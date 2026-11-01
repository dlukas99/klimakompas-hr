"""`kk sources verify`: status, type, robots.txt, sample, records and Portal metadata."""

import io
import json
import re
import zipfile
from datetime import UTC, date, datetime, timedelta
from functools import reduce
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import structlog
from lxml import etree
from pydantic import BaseModel, Field

from klimakompas.core.config import CountSpec, Probe, Source
from klimakompas.core.http import HttpClient
from klimakompas.core.raw import save_raw

log = structlog.get_logger()

CKAN_API = "https://data.gov.hr/ckan/api/3/action"
MAX_FIXTURE_BYTES = 256 * 1024
MAX_RAW_BYTES = 8 * 1024 * 1024
SAMPLE_CHARS = 120
EMAIL = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}")
EMAIL_PLACEHOLDER = b"removed@example.invalid"


class RobotsRules:
    """robots.txt rules following RFC 9309: 4xx means no rules, 5xx or no answer means disallow."""

    def __init__(self, state: str, parser: RobotFileParser | None = None) -> None:
        self.state = state
        self._parser = parser

    def allows(self, user_agent: str, url: str) -> bool:
        if self.state == "nedostupan":
            return False
        return self._parser is None or self._parser.can_fetch(user_agent, url)


def fetch_robots(client: HttpClient, host: str) -> RobotsRules:
    try:
        response = client.request("GET", f"https://{host}/robots.txt")
    except httpx.HTTPError:
        return RobotsRules("nedostupan")
    if response.status_code >= 500:
        return RobotsRules("nedostupan")
    if response.status_code >= 400:
        return RobotsRules(f"nema datoteke ({response.status_code})")
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return RobotsRules("pravila pročitana", parser)


class ProbeResult(BaseModel):
    url: str
    method: str
    status: int | None = None
    content_type: str | None = None
    size: int | None = None
    last_modified: str | None = None
    etag: str | None = None
    records: int | None = None
    sample: str | None = None
    range_supported: bool | None = None
    robots_allowed: bool = True
    error: str | None = None
    empty_ok: bool = False

    @property
    def ok(self) -> bool:
        if not self.robots_allowed or self.error or self.status is None:
            return False
        if not 200 <= self.status < 300:
            return False
        return self.records != 0 or self.empty_ok


class PortalInfo(BaseModel):
    package_id: str | None = None
    title: str | None = None
    organization: str | None = None
    license: str | None = None
    modified: str | None = None
    candidates: list[str] = Field(default_factory=list)
    error: str | None = None


class SourceResult(BaseModel):
    source: Source
    robots: dict[str, str] = Field(default_factory=dict)
    probes: list[ProbeResult] = Field(default_factory=list)
    portal: PortalInfo | None = None
    checked_at: datetime

    @property
    def ok(self) -> bool:
        return all(probe.ok for probe in self.probes)


def scrub_emails(body: bytes) -> bytes:
    """Fixtures are public, so personal contact details in metadata are not kept."""
    return EMAIL.sub(EMAIL_PLACEHOLDER, body)


def count_records(body: bytes, spec: CountSpec) -> int:
    if spec.kind == "xml_tag":
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
        root = etree.fromstring(body, parser=parser)
        return sum(1 for element in root.iter(f"{{*}}{spec.tag}"))
    if spec.kind in ("json_list", "json_value"):
        value: Any = json.loads(body)
        if spec.path:
            value = reduce(lambda node, key: node[key], spec.path.split("."), value)
        return len(value) if spec.kind == "json_list" else int(value)
    raise ValueError(f"count kind {spec.kind} needs no response body")


class _RangeFile(io.RawIOBase):
    """Seekable view of a remote file, so a ZIP directory can be read without downloading it."""

    def __init__(self, client: HttpClient, url: str, size: int) -> None:
        self._client = client
        self._url = url
        self._size = size
        self._position = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._position, io.SEEK_END: self._size}[whence]
        self._position = base + offset
        return self._position

    def readinto(self, buffer: Any) -> int:
        end = min(self._position + len(buffer), self._size)
        if self._position >= end:
            return 0
        headers = {"Range": f"bytes={self._position}-{end - 1}"}
        response = self._client.request("GET", self._url, headers=headers)
        response.raise_for_status()
        if response.status_code != 206:
            raise OSError("server ignored the Range header")
        chunk = response.content
        buffer[: len(chunk)] = chunk
        self._position += len(chunk)
        return len(chunk)


def _expand(url: str, today: date) -> str:
    return url.replace("{date_from}", (today - timedelta(days=3)).strftime("%d.%m.%Y")).replace(
        "{date_to}", (today - timedelta(days=1)).strftime("%d.%m.%Y")
    )


def _fill_headers(result: ProbeResult, response: httpx.Response) -> None:
    result.status = response.status_code
    result.content_type = response.headers.get("Content-Type")
    result.last_modified = response.headers.get("Last-Modified")
    result.etag = response.headers.get("ETag")
    length = response.headers.get("Content-Length")
    result.size = int(length) if length and length.isdigit() else len(response.content)


def _run_probe(
    client: HttpClient,
    source: Source,
    probe: Probe,
    url: str,
    data_dir: Path,
    fixtures_dir: Path | None,
) -> ProbeResult:
    result = ProbeResult(url=url, method=probe.method, empty_ok=probe.expect_empty_ok)
    if probe.method == "HEAD":
        _fill_headers(result, client.request("HEAD", url))
    elif probe.method in ("RANGE", "ZIP"):
        response = client.request("GET", url, headers={"Range": "bytes=0-1023"})
        _fill_headers(result, response)
        result.range_supported = response.status_code == 206
        total = response.headers.get("Content-Range", "/").rsplit("/", 1)[-1]
        if total.isdigit():
            result.size = int(total)
        if probe.method == "ZIP" and result.range_supported and result.size:
            remote = io.BufferedReader(_RangeFile(client, url, result.size), 1024 * 1024)
            with zipfile.ZipFile(remote) as archive:
                names = archive.namelist()
            result.records = len(names)
            result.sample = ", ".join(names[:4])
    else:
        response = client.request("GET", url)
        _fill_headers(result, response)
        body = response.content
        if response.is_success:
            result.sample = response.text[:SAMPLE_CHARS].replace("\n", " ").strip()
            if probe.count:
                result.records = count_records(body, probe.count)
            if len(body) <= MAX_RAW_BYTES:
                name = probe.fixture or _file_name(url)
                save_raw(data_dir, source.id, name, response, source.license)
            if fixtures_dir and probe.fixture and len(body) <= MAX_FIXTURE_BYTES:
                folder = fixtures_dir / source.id
                folder.mkdir(parents=True, exist_ok=True)
                (folder / probe.fixture).write_bytes(scrub_emails(body))
    return result


def _file_name(url: str) -> str:
    return Path(urlsplit(url).path).name or "response"


def _portal_info(client: HttpClient, source: Source) -> PortalInfo | None:
    plan = source.verify
    if not source.data_gov_hr_id and not plan.portal_query:
        return None
    try:
        if source.data_gov_hr_id:
            response = client.request(
                "GET", f"{CKAN_API}/package_show", params={"id": source.data_gov_hr_id}
            )
            response.raise_for_status()
            package = response.json()["result"]
            organization = package.get("organization") or {}
            return PortalInfo(
                package_id=package["name"],
                title=package.get("title"),
                organization=organization.get("title"),
                license=package.get("license_title"),
                modified=package.get("metadata_modified"),
            )
        response = client.request(
            "GET", f"{CKAN_API}/package_search", params={"q": plan.portal_query, "rows": 5}
        )
        response.raise_for_status()
        return PortalInfo(candidates=[p["name"] for p in response.json()["result"]["results"]])
    except (httpx.HTTPError, KeyError, ValueError) as error:
        return PortalInfo(error=f"{type(error).__name__}: {error}")


def verify_source(
    client: HttpClient,
    source: Source,
    robots_cache: dict[str, RobotsRules],
    user_agent: str,
    data_dir: Path,
    fixtures_dir: Path | None,
    today: date,
) -> SourceResult:
    result = SourceResult(source=source, checked_at=datetime.now(UTC))
    plan = source.verify
    hosts = list(plan.robots_hosts)

    urls = [_expand(probe.url, today) for probe in plan.probes]
    hosts.extend(urlsplit(url).netloc for url in urls)
    for host in dict.fromkeys(hosts):
        if host not in robots_cache:
            robots_cache[host] = fetch_robots(client, host)
        rules = robots_cache[host]
        allowed = rules.allows(user_agent, f"https://{host}/")
        result.robots[host] = rules.state + ("" if allowed else ", dohvat nije dopušten")

    if plan.policy != "auto":
        result.portal = _portal_info(client, source)
        return result

    for probe, url in zip(plan.probes, urls, strict=True):
        rules = robots_cache[urlsplit(url).netloc]
        if not rules.allows(user_agent, url):
            log.warning("robots.txt disallows probe", source=source.id, url=url)
            result.probes.append(ProbeResult(url=url, method=probe.method, robots_allowed=False))
            continue
        try:
            result.probes.append(_run_probe(client, source, probe, url, data_dir, fixtures_dir))
        except (
            httpx.HTTPError,
            OSError,
            ValueError,
            KeyError,
            etree.XMLSyntaxError,
            zipfile.BadZipFile,
        ) as error:
            log.warning("probe failed", source=source.id, url=url, error=str(error))
            result.probes.append(
                ProbeResult(url=url, method=probe.method, error=f"{type(error).__name__}: {error}")
            )
    result.portal = _portal_info(client, source)
    return result


def verify_sources(
    sources: list[Source],
    client: HttpClient,
    data_dir: Path,
    fixtures_dir: Path | None = None,
    today: date | None = None,
) -> list[SourceResult]:
    robots_cache: dict[str, RobotsRules] = {}
    return [
        verify_source(
            client,
            source,
            robots_cache,
            client.user_agent,
            data_dir,
            fixtures_dir,
            today or datetime.now(UTC).date(),
        )
        for source in sources
    ]


def has_p0_failure(results: list[SourceResult]) -> bool:
    return any(
        result.source.priority.startswith("P0") and not result.ok and _is_autochecked(result)
        for result in results
    )


def _is_autochecked(result: SourceResult) -> bool:
    return result.source.verify.policy == "auto"


def _number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _size(value: int | None) -> str:
    if value is None:
        return "–"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f} MB".replace(".", ",")
    return f"{value / 1000:.1f} kB".replace(".", ",")


def _status_label(result: SourceResult) -> str:
    if result.source.verify.policy != "auto":
        return "➖ bez automatskog dohvata"
    if not result.probes:
        return "➖ nema provjere"
    if result.ok:
        return "✅ radi"
    if any(not probe.robots_allowed for probe in result.probes):
        return "⛔ robots.txt ne dopušta"
    return "❌ greška"


def _cell(value: str | None) -> str:
    return (value or "–").replace("|", "\\|").replace("\n", " ")


def _probe_lines(probe: ProbeResult) -> list[str]:
    if not probe.robots_allowed:
        return [f"- ⛔ `{probe.url}`: nije dohvaćeno, robots.txt ne dopušta"]
    if probe.error:
        return [f"- ❌ `{probe.url}`: {_cell(probe.error)}"]
    mark = "✅" if probe.ok else "❌"
    parts = [f"HTTP {probe.status}", _cell(probe.content_type), _size(probe.size)]
    if probe.records is not None:
        parts.append(f"zapisa: {_number(probe.records)}")
    if probe.range_supported is not None:
        parts.append(f"Range: {'da' if probe.range_supported else 'ne'}")
    if probe.last_modified:
        parts.append(f"Last-Modified: {probe.last_modified}")
    lines = [f"- {mark} `{probe.method} {probe.url}`: " + " · ".join(parts)]
    if probe.sample:
        lines.append(f"  - uzorak: `{probe.sample.replace('`', chr(39))}`")
    return lines


def render_report(results: list[SourceResult]) -> str:
    checked = max((result.checked_at for result in results), default=datetime.now(UTC))
    lines = [
        "# Provjera izvora podataka",
        "",
        "Datoteku generira `make sources-verify`. Bilješke dolaze iz `config/sources.yaml`.",
        "",
        f"Zadnja provjera: {checked:%d. %m. %Y. u %H:%M} UTC.",
        "",
        "| Izvor | Prioritet | Stanje | Licenca |",
        "|---|---|---|---|",
    ]
    for result in results:
        source = result.source
        lines.append(
            f"| `{source.id}` | {source.priority} | {_status_label(result)} "
            f"| {_cell(source.license)} |"
        )
    for result in results:
        source = result.source
        lines += ["", f"## `{source.id}`: {source.name}", "", f"- Izdavač: {source.publisher}"]
        for host, state in result.robots.items():
            lines.append(f"- robots.txt `{host}`: {state}")
        for probe in result.probes:
            lines += _probe_lines(probe)
        portal = result.portal
        if portal:
            if portal.error:
                lines.append(f"- Portal: provjera nije uspjela ({_cell(portal.error)})")
            elif portal.package_id:
                lines.append(
                    f"- Portal: `{portal.package_id}` · {_cell(portal.organization)} · "
                    f"licenca: {_cell(portal.license)} · izmjena: {_cell(portal.modified)}"
                )
            elif portal.candidates:
                names = ", ".join(f"`{name}`" for name in portal.candidates)
                lines.append(f"- Portal, kandidati iz pretrage: {names}")
            else:
                lines.append("- Portal: pretraga nije našla zapis")
        if source.verification.note:
            lines.append(f"- Bilješka ({source.verification.date:%d. %m. %Y.}): ")
            lines[-1] += source.verification.note.strip()
    return "\n".join(lines) + "\n"
