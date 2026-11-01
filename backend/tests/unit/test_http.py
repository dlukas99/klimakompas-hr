import threading
from unittest import mock

import httpx
import pytest

from klimakompas.core.http import MAX_PER_HOST, HttpClient

UA = "KlimaKompasHR/test"


def client_for(handler: httpx.MockTransport) -> HttpClient:
    return HttpClient(UA, transport=handler)


@pytest.fixture(autouse=True)
def no_sleep() -> object:
    with mock.patch("tenacity.nap.time.sleep") as sleep:
        yield sleep


def test_sends_user_agent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=request.headers["User-Agent"])

    with client_for(httpx.MockTransport(handler)) as client:
        assert client.request("GET", "https://a.test/").text == UA


def test_retries_then_succeeds() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503 if len(calls) < 3 else 200)

    with client_for(httpx.MockTransport(handler)) as client:
        assert client.request("GET", "https://a.test/").status_code == 200
    assert len(calls) == 3


def test_returns_last_response_when_retries_run_out() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    with client_for(httpx.MockTransport(handler)) as client:
        assert client.request("GET", "https://a.test/").status_code == 500
    assert len(calls) == 3


def test_does_not_retry_client_errors() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(404)

    with client_for(httpx.MockTransport(handler)) as client:
        client.request("GET", "https://a.test/")
    assert len(calls) == 1


def test_honours_retry_after(no_sleep: mock.Mock) -> None:
    responses = [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200)]

    def handler(_: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    with client_for(httpx.MockTransport(handler)) as client:
        client.request("GET", "https://a.test/")
    no_sleep.assert_called_once_with(7.0)


def test_raises_transport_error_after_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with client_for(httpx.MockTransport(handler)) as client, pytest.raises(httpx.ConnectError):
        client.request("GET", "https://a.test/")


def test_conditional_get_sends_validators() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["If-None-Match"] == '"abc"'
        assert request.headers["If-Modified-Since"] == "Sun, 01 Nov 2026 16:00:00 GMT"
        return httpx.Response(304)

    with client_for(httpx.MockTransport(handler)) as client:
        response = client.get(
            "https://a.test/", etag='"abc"', last_modified="Sun, 01 Nov 2026 16:00:00 GMT"
        )
    assert response.status_code == 304


def test_limits_parallel_requests_per_host() -> None:
    lock = threading.Lock()
    active = 0
    peak = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        # The autouse fixture patches time.sleep, so overlap needs a real wait.
        threading.Event().wait(0.02)
        with lock:
            active -= 1
        return httpx.Response(200)

    with client_for(httpx.MockTransport(handler)) as client:
        threads = [
            threading.Thread(target=client.request, args=("GET", "https://a.test/"))
            for _ in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    assert peak == MAX_PER_HOST
