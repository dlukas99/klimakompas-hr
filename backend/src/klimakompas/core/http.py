"""The only HTTP client for external sources (SPEC §4.1)."""

import threading
from collections import defaultdict
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from tenacity import RetryCallState, Retrying, retry_if_exception, stop_after_attempt
from tenacity.wait import wait_exponential

TIMEOUTS = {"batch": 30.0, "live": 5.0}
MAX_PER_HOST = 2
MAX_ATTEMPTS = 3
MAX_RETRY_AFTER_S = 60.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class _RetryableStatus(Exception):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"HTTP {response.status_code}")
        self.response = response


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError):
            return None
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_S)


_backoff = wait_exponential(multiplier=1, min=1, max=8)


def _wait(state: RetryCallState) -> float:
    outcome = state.outcome
    error = outcome.exception() if outcome else None
    if isinstance(error, _RetryableStatus):
        retry_after = _retry_after_seconds(error.response)
        if retry_after is not None:
            return retry_after
    return _backoff(state)


def _is_retryable(error: BaseException) -> bool:
    return isinstance(error, _RetryableStatus | httpx.TransportError)


def _return_last_response(state: RetryCallState) -> httpx.Response:
    outcome = state.outcome
    assert outcome is not None
    error = outcome.exception()
    if isinstance(error, _RetryableStatus):
        return error.response
    assert error is not None
    raise error


class HttpClient:
    def __init__(
        self,
        user_agent: str,
        profile: Literal["batch", "live"] = "batch",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.user_agent = user_agent
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=TIMEOUTS[profile],
            follow_redirects=True,
            transport=transport,
        )
        self._host_slots: defaultdict[str, threading.BoundedSemaphore] = defaultdict(
            lambda: threading.BoundedSemaphore(MAX_PER_HOST)
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        host = urlsplit(url).netloc

        def attempt() -> httpx.Response:
            # The slot is held per attempt, so backoff sleeps do not block the host.
            with self._host_slots[host]:
                response = self._client.request(method, url, **kwargs)
            if response.status_code in RETRYABLE_STATUS:
                raise _RetryableStatus(response)
            return response

        retrying = Retrying(
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=_wait,
            retry=retry_if_exception(_is_retryable),
            retry_error_callback=_return_last_response,
        )
        return retrying(attempt)

    def get(
        self, url: str, etag: str | None = None, last_modified: str | None = None
    ) -> httpx.Response:
        """Conditional GET; a 304 response means the stored copy is still current."""
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return self.request("GET", url, headers=headers)
