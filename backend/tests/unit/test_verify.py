import io
import zipfile
from datetime import date
from pathlib import Path

import httpx
import pytest

from klimakompas.core.config import CountSpec, Source
from klimakompas.core.http import HttpClient
from klimakompas.sources.verify import (
    ProbeResult,
    count_records,
    fetch_robots,
    has_p0_failure,
    render_report,
    scrub_emails,
    verify_sources,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
UA = "KlimaKompasHR/test"


def make_source(**overrides: object) -> Source:
    values: dict[str, object] = {
        "id": "demo",
        "name": "Demo",
        "publisher": "Izdavač",
        "access": {"type": "rest"},
        "format": "json",
        "license": "CC BY 4.0",
        "attribution": "Izvor: demo",
        "used_for": ["test"],
        "priority": "P0",
        "verification": {"status": "verified", "date": "2026-11-01", "note": "Bilješka."},
    }
    values.update(overrides)
    return Source.model_validate(values)


def run(source: Source, handler: httpx.MockTransport, tmp_path: Path) -> list[ProbeResult]:
    with HttpClient(UA, transport=handler) as client:
        results = verify_sources([source], client, tmp_path, today=date(2026, 11, 1))
    return results[0].probes


def test_scrubs_emails_from_fixtures() -> None:
    assert scrub_emails(b"<a>ime.prezime@dgu.hr</a>") == b"<a>removed@example.invalid</a>"
    for path in FIXTURES.rglob("*"):
        if path.is_file():
            assert scrub_emails(path.read_bytes()) == path.read_bytes(), path


def test_counts_real_cap_warnings() -> None:
    body = (FIXTURES / "dhmz_cap" / "cap_hr_today.xml").read_bytes()
    assert count_records(body, CountSpec(kind="xml_tag", tag="info")) > 0


def test_counts_real_fire_index_stations() -> None:
    body = (FIXTURES / "dhmz_fire_index" / "indeks.xml").read_bytes()
    assert count_records(body, CountSpec(kind="xml_tag", tag="postaja")) > 0


def test_counts_real_azo_records() -> None:
    body = (FIXTURES / "azo_aq_rest" / "zagreb1_pm10_hourly.json").read_bytes()
    assert count_records(body, CountSpec(kind="json_list")) > 0


def test_counts_real_ckan_total() -> None:
    body = (FIXTURES / "ckan" / "package_search.json").read_bytes()
    assert count_records(body, CountSpec(kind="json_value", path="result.count")) > 0


def test_parses_latin1_heatwave_fixture() -> None:
    body = (FIXTURES / "dhmz_heatwave" / "toplinskival_off_season.xml").read_bytes()
    assert count_records(body, CountSpec(kind="xml_tag", tag="section")) == 1


@pytest.mark.parametrize(
    ("status", "body", "allowed"),
    [
        (200, "User-agent: *\nDisallow: /", False),
        (200, "User-agent: *\nAllow: /", True),
        (200, "<html>not robots</html>", True),
        (404, "", True),
        (503, "", False),
    ],
)
def test_robots_rules_follow_rfc_9309(status: int, body: str, allowed: bool) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status, text=body))
    with HttpClient(UA, transport=transport) as client:
        assert fetch_robots(client, "a.test").allows(UA, "https://a.test/x") is allowed


def test_disallowed_probe_is_never_requested(tmp_path: Path) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(200, text="User-agent: *\nDisallow: /")

    source = make_source(verify={"probes": [{"url": "https://a.test/data.json"}]})
    probes = run(source, httpx.MockTransport(handler), tmp_path)
    assert requested == ["/robots.txt"]
    assert probes[0].robots_allowed is False
    assert probes[0].ok is False


def test_robots_only_policy_never_requests_the_service(tmp_path: Path) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(503)

    source = make_source(verify={"policy": "robots_only", "robots_hosts": ["a.test"]})
    run(source, httpx.MockTransport(handler), tmp_path)
    assert set(requested) == {"/robots.txt"}


def test_api_terms_policy_reports_robots_but_runs_probes(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /")
        return httpx.Response(200, json={"a": 1})

    source = make_source(
        verify={"policy": "api_terms", "probes": [{"url": "https://a.test/v1/data"}]}
    )
    with HttpClient(UA, transport=httpx.MockTransport(handler)) as client:
        result = verify_sources([source], client, tmp_path, today=date(2026, 11, 1))[0]
    assert result.probes[0].ok
    assert "dohvat nije dopušten" in result.robots["a.test"]


def test_stores_raw_response_with_metadata(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, json=[{"a": 1}], headers={"ETag": '"x"'})

    source = make_source(
        verify={"probes": [{"url": "https://a.test/d.json", "count": {"kind": "json_list"}}]}
    )
    probes = run(source, httpx.MockTransport(handler), tmp_path)
    assert probes[0].ok and probes[0].records == 1
    stored = list((tmp_path / "raw" / "demo").glob("*/d.json"))
    assert len(stored) == 1
    assert '"etag": "\\"x\\""' in (stored[0].parent / "meta.json").read_text(encoding="utf-8")


def test_expands_date_placeholders_for_azo_format(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(404 if request.url.path == "/robots.txt" else 200, json=[])

    url = "https://a.test/d?od={date_from}&do={date_to}"
    source = make_source(verify={"probes": [{"url": url, "expect_empty_ok": True}]})
    run(source, httpx.MockTransport(handler), tmp_path)
    assert seen[-1].endswith("od=29.10.2026&do=31.10.2026")


def test_zip_probe_lists_entries_without_full_download(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.gml", "x" * 5000)
        archive.writestr("b.gml", "y")
    payload = buffer.getvalue()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        start, end = request.headers["Range"].removeprefix("bytes=").split("-")
        chunk = payload[int(start) : int(end) + 1]
        return httpx.Response(
            206,
            content=chunk,
            headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
        )

    source = make_source(verify={"probes": [{"url": "https://a.test/a.zip", "method": "ZIP"}]})
    probes = run(source, httpx.MockTransport(handler), tmp_path)
    assert probes[0].records == 2
    assert probes[0].range_supported is True
    assert probes[0].sample == "a.gml, b.gml"


def test_failed_p0_probe_is_reported_and_blocks(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    source = make_source(verify={"probes": [{"url": "https://a.test/gone"}]})
    with HttpClient(UA, transport=httpx.MockTransport(handler)) as client:
        results = verify_sources([source], client, tmp_path, today=date(2026, 11, 1))
    assert has_p0_failure(results) is True
    report = render_report(results)
    assert "❌" in report
    assert "Bilješka." in report


def test_report_marks_sources_without_automated_access(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(503))
    source = make_source(
        priority="P1", verify={"policy": "robots_only", "robots_hosts": ["a.test"]}
    )
    with HttpClient(UA, transport=transport) as client:
        results = verify_sources([source], client, tmp_path, today=date(2026, 11, 1))
    assert has_p0_failure(results) is False
    assert "bez automatskog dohvata" in render_report(results)
