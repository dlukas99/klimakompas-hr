"""Live connectors run by the worker. If a run fails, the last good data stays (SPEC §8)."""

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import text

from klimakompas.core.config import load_sources, load_thresholds
from klimakompas.core.db import get_engine, upsert_rows
from klimakompas.core.raw import save_raw
from klimakompas.live.parsers import (
    AqObservation,
    CapWarning,
    county_key,
    parse_aq,
    parse_cap,
    parse_fire_index,
    parse_heatwave,
    parse_stations,
)
from klimakompas.sources.base import LoadResult, RunContext, record

log = structlog.get_logger()

AZO_BASE = "https://iszz.azo.hr/iskzl/rs"
# Pollutant ids from the AZO service manual: PM10, PM2.5, NO2 and O3.
AZO_POLLUTANTS = {"5": "pm10", "28": "pm25", "1": "no2", "31": "o3"}
AZO_HOURLY = 0
AZO_MIN_INTERVAL_S = 4.0
AZO_WINDOW_DAYS = 2
AZO_ACTIVE_DAYS = 7
AZO_PROBE_LIMIT = 40
AZO_PROBE_INTERVAL = timedelta(hours=24)


def _get(ctx: RunContext, url: str, filename: str | None = None) -> httpx.Response:
    response = ctx.client.get(url)
    response.raise_for_status()
    if filename:
        save_raw(ctx.data_dir, ctx.source.id, filename, response, ctx.source.license)
    return response


class CapConnector:
    source_id = "dhmz_cap"

    def fetch(self, ctx: RunContext) -> list[bytes]:
        return [_get(ctx, url, url.rsplit("/", 1)[-1]).content for url in ctx.source.access["urls"]]

    def parse(self, artifacts: list[bytes]) -> list[CapWarning]:
        return [warning for body in artifacts for warning in parse_cap(body)]

    def load(self, frame: list[CapWarning], ctx: RunContext) -> LoadResult:
        conn = ctx.db
        counties = {
            county_key(row.name): row.code
            for row in conn.execute(text("SELECT code, name FROM ref.zupanije"))
        }
        now = datetime.now(UTC)
        conn.execute(
            text("DELETE FROM live.warnings WHERE source_id = :id"), {"id": self.source_id}
        )
        count = upsert_rows(
            conn,
            "live.warnings",
            (
                "id",
                "source_id",
                "event",
                "awareness_type",
                "level",
                "level_name",
                "severity",
                "onset",
                "expires",
                "region_id",
                "nuts3",
                "zupanija_code",
                "area_desc",
                "description",
                "instruction",
                "fetched_at",
            ),
            ("id",),
            (
                (
                    w.id,
                    self.source_id,
                    w.event,
                    w.awareness_type,
                    w.level,
                    w.level_name,
                    w.severity,
                    w.onset,
                    w.expires,
                    w.region_id,
                    w.nuts3,
                    # Sea regions have no county; they stay stored but are not tied to land cells.
                    counties.get(county_key(w.area_desc)),
                    w.area_desc,
                    w.description,
                    w.instruction,
                    now,
                )
                for w in frame
            ),
        )
        record(ctx, "warnings", count)
        return LoadResult(rows=count)


class HeatwaveConnector:
    source_id = "dhmz_heatwave"

    def fetch(self, ctx: RunContext) -> list[bytes]:
        url = ctx.source.access["urls"][0]
        return [_get(ctx, url, "toplinskival.xml").content]

    def parse(self, artifacts: list[bytes]) -> dict[str, Any]:
        return parse_heatwave(artifacts[0])

    def load(self, frame: dict[str, Any], ctx: RunContext) -> LoadResult:
        upsert_rows(
            ctx.db,
            "live.heatwave",
            ("id", "level", "raw", "fetched_at"),
            ("id",),
            [
                (
                    "current",
                    "active" if frame["active"] else "none",
                    json.dumps(frame, ensure_ascii=False),
                    datetime.now(UTC),
                )
            ],
        )
        return LoadResult(rows=1)


class FireIndexConnector:
    source_id = "dhmz_fire_index"

    def fetch(self, ctx: RunContext) -> list[bytes]:
        return [_get(ctx, ctx.source.access["urls"][0], "indeks.xml").content]

    def parse(self, artifacts: list[bytes]) -> Any:
        return parse_fire_index(artifacts[0])

    def load(self, frame: Any, ctx: RunContext) -> LoadResult:
        day, stations = frame
        months = load_thresholds()["fire_index"]["season_months"]
        in_season = day is not None and day.month in months
        now = datetime.now(UTC)
        count = upsert_rows(
            ctx.db,
            "live.fire_index",
            (
                "station_code",
                "station_name",
                "fwi",
                "category",
                "index_date",
                "in_season",
                "fetched_at",
            ),
            ("station_code",),
            ((s.code, s.name, s.fwi, s.category, day, in_season, now) for s in stations),
        )
        # DHMZ gives no coordinates, so a station takes the position of its namesake settlement.
        ctx.db.execute(
            text(
                """
                UPDATE live.fire_index f SET naselje_code = m.code, geom = m.point
                FROM (
                    SELECT DISTINCT ON (f2.station_code) f2.station_code, n.code, n.point
                    FROM live.fire_index f2
                    JOIN ref.naselja n ON n.search_text = ref.normalize_search(f2.station_name)
                    LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code
                    ORDER BY f2.station_code, p.pop_total DESC NULLS LAST
                ) m
                WHERE m.station_code = f.station_code
                """
            )
        )
        return LoadResult(rows=count)


@dataclass(frozen=True)
class AzoBatch:
    stations: list[Any]
    observations: list[tuple[str, str, AqObservation]]
    checked: list[tuple[str, str]]


class AzoConnector:
    """Polls series with recent data on every run and probes a few idle ones for new data."""

    source_id = "azo_aq_rest"

    def _pause(self) -> None:
        # The service answers HTTP 429 to fast clients, with no Retry-After header.
        threading.Event().wait(AZO_MIN_INTERVAL_S)

    def _series(self, stations: list[Any]) -> list[tuple[str, str]]:
        now = datetime.now(UTC)
        with get_engine().connect() as conn:
            state = {
                (row.station_id, row.pollutant_id): row
                for row in conn.execute(text("SELECT * FROM live.aq_series"))
            }
        active: list[tuple[str, str]] = []
        idle: list[tuple[datetime, str, str]] = []
        oldest = datetime.min.replace(tzinfo=UTC)
        for station in stations:
            for pollutant in AZO_POLLUTANTS:
                row = state.get((station.id, pollutant))
                if (
                    row
                    and row.last_obs_at
                    and now - row.last_obs_at < timedelta(days=AZO_ACTIVE_DAYS)
                ):
                    active.append((station.id, pollutant))
                elif not row or not row.last_checked_at:
                    idle.append((oldest, station.id, pollutant))
                elif now - row.last_checked_at > AZO_PROBE_INTERVAL:
                    idle.append((row.last_checked_at, station.id, pollutant))
        idle.sort()
        return active + [(station, pollutant) for _, station, pollutant in idle[:AZO_PROBE_LIMIT]]

    def fetch(self, ctx: RunContext) -> AzoBatch:
        form = _get(ctx, f"{AZO_BASE}/podatak/frm/gg?t=false&i=false").json()
        self._pause()
        coordinates = _get(ctx, f"{AZO_BASE}/postaja/koordinate").json()
        stations = parse_stations(form, coordinates)
        today = datetime.now(UTC).date()
        start = (today - timedelta(days=AZO_WINDOW_DAYS)).strftime("%d.%m.%Y")
        end = (today + timedelta(days=1)).strftime("%d.%m.%Y")
        observations: list[tuple[str, str, AqObservation]] = []
        checked: list[tuple[str, str]] = []
        for station, pollutant in self._series(stations):
            self._pause()
            url = (
                f"{AZO_BASE}/podatak/export/json?postaja={station}&polutant={pollutant}"
                f"&tipPodatka={AZO_HOURLY}&vrijemeOd={start}&vrijemeDo={end}"
            )
            try:
                response = _get(ctx, url)
            except httpx.HTTPError as error:
                # One bad series must not throw away what the others returned.
                log.warning("azo series failed", station=station, error=type(error).__name__)
                continue
            checked.append((station, pollutant))
            observations.extend((station, pollutant, item) for item in parse_aq(response.json()))
        return AzoBatch(stations, observations, checked)

    def parse(self, artifacts: AzoBatch) -> AzoBatch:
        return artifacts

    def load(self, frame: AzoBatch, ctx: RunContext) -> LoadResult:
        conn = ctx.db
        upsert_rows(
            conn,
            "live.aq_stations",
            ("station_id", "name", "network"),
            ("station_id",),
            ((s.id, s.name, s.network) for s in frame.stations),
        )
        for station in frame.stations:
            if station.lat is not None and station.lon is not None:
                conn.execute(
                    text(
                        "UPDATE live.aq_stations SET geom = ST_Transform(ST_SetSRID("
                        "ST_MakePoint(:lon, :lat), 4326), 3035) WHERE station_id = :id"
                    ),
                    {"lon": station.lon, "lat": station.lat, "id": station.id},
                )
        count = upsert_rows(
            conn,
            "live.aq_obs",
            ("station_id", "pollutant_id", "ts", "value", "unit"),
            ("station_id", "pollutant_id", "ts"),
            ((s, p, o.ts, o.value, o.unit) for s, p, o in frame.observations),
        )
        now = datetime.now(UTC)
        for station, pollutant in frame.checked:
            conn.execute(
                text(
                    """
                    INSERT INTO live.aq_series
                        (station_id, pollutant_id, last_checked_at, last_obs_at)
                    VALUES (:station, :pollutant, :now, (
                        SELECT max(ts) FROM live.aq_obs
                        WHERE station_id = :station AND pollutant_id = :pollutant))
                    ON CONFLICT (station_id, pollutant_id) DO UPDATE SET
                        last_checked_at = EXCLUDED.last_checked_at,
                        last_obs_at = EXCLUDED.last_obs_at
                    """
                ),
                {"station": station, "pollutant": pollutant, "now": now},
            )
        conn.execute(
            text(
                "UPDATE live.aq_stations s SET last_obs_at = o.ts FROM "
                "(SELECT station_id, max(ts) AS ts FROM live.aq_obs GROUP BY 1) o "
                "WHERE o.station_id = s.station_id"
            )
        )
        record(ctx, "series_checked", len(frame.checked))
        return LoadResult(rows=count)


class CkanConnector:
    """Portal metadata for each source that has a Portal record."""

    source_id = "ckan"

    def fetch(self, ctx: RunContext) -> list[dict[str, Any]]:
        rows = []
        for source in load_sources():
            if not source.data_gov_hr_id:
                continue
            url = f"{ctx.source.access['package_show']}?id={source.data_gov_hr_id}"
            try:
                body = _get(ctx, url).json()
            except (httpx.HTTPError, ValueError) as error:
                log.warning("ckan record failed", source=source.id, error=type(error).__name__)
                continue
            result = body.get("result") or {}
            rows.append(
                {
                    "source_id": source.id,
                    "package_id": result.get("id"),
                    "title": result.get("title"),
                    "organization": (result.get("organization") or {}).get("title"),
                    "license_title": result.get("license_title"),
                    "metadata_modified": result.get("metadata_modified"),
                }
            )
        return rows

    def parse(self, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return artifacts

    def load(self, frame: list[dict[str, Any]], ctx: RunContext) -> LoadResult:
        now = datetime.now(UTC)
        count = upsert_rows(
            ctx.db,
            "meta.ckan_metadata",
            (
                "source_id",
                "package_id",
                "title",
                "organization",
                "license_title",
                "metadata_modified",
                "fetched_at",
            ),
            ("source_id",),
            (
                (
                    r["source_id"],
                    r["package_id"],
                    r["title"],
                    r["organization"],
                    r["license_title"],
                    r["metadata_modified"],
                    now,
                )
                for r in frame
            ),
        )
        return LoadResult(rows=count)


NATURE_LAYERS = (
    "dzzpnpis:zasticeno_podrucje_poligoni",
    "dzzpnpis:n2krh2023stanista",
    "dzzpnpis:n2krh2023ptice",
    "dzzpnpis:ramsar",
)


def _first_text(properties: dict[str, Any], names: tuple[str, ...]) -> str | None:
    lowered = {key.lower(): value for key, value in properties.items()}
    for name in names:
        value = lowered.get(name)
        if value not in (None, ""):
            return str(value)
    return None


class BioportalConnector:
    source_id = "bioportal_wfs"

    def fetch(self, ctx: RunContext) -> list[tuple[str, dict[str, Any]]]:
        endpoint = ctx.source.access["endpoint"]
        layers = []
        for layer in NATURE_LAYERS:
            url = (
                f"{endpoint}?service=WFS&version=2.0.0&request=GetFeature&typeNames={layer}"
                "&outputFormat=application/json&srsName=EPSG:4326"
            )
            response = ctx.client.request("GET", url, timeout=180.0)
            response.raise_for_status()
            log.info("bioportal layer", layer=layer, size=len(response.content))
            layers.append((layer, response.json()))
        return layers

    def parse(self, artifacts: list[tuple[str, dict[str, Any]]]) -> list[tuple[Any, ...]]:
        rows = []
        for layer, collection in artifacts:
            short = layer.split(":", 1)[1]
            for position, feature in enumerate(collection["features"]):
                if not feature.get("geometry"):
                    continue
                properties = feature.get("properties") or {}
                rows.append(
                    (
                        f"{short}:{feature.get('id', position)}",
                        short,
                        _first_text(properties, NATURE_NAME_FIELDS),
                        _first_text(properties, NATURE_CATEGORY_FIELDS),
                        json.dumps(feature["geometry"]),
                    )
                )
        return rows

    def load(self, frame: list[tuple[Any, ...]], ctx: RunContext) -> LoadResult:
        if not frame:
            raise ValueError("Bioportal returned no features")
        conn = ctx.db
        now = datetime.now(UTC)
        conn.execute(
            text(
                "CREATE TEMP TABLE _nature (id text, layer text, name text, category text, g text) "
                "ON COMMIT DROP"
            )
        )
        cursor = conn.connection.driver_connection.cursor()  # type: ignore[union-attr]
        with cursor.copy("COPY _nature (id, layer, name, category, g) FROM STDIN") as copy:
            for row in frame:
                copy.write_row(row)
        conn.execute(
            text(
                """
                INSERT INTO live.nature_areas (id, layer, name, category, geom, fetched_at)
                SELECT id, layer, name, category,
                       ST_Transform(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(g), 4326)), 3035),
                       :now
                FROM _nature
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, category = EXCLUDED.category,
                    geom = EXCLUDED.geom, fetched_at = EXCLUDED.fetched_at
                """
            ),
            {"now": now},
        )
        conn.execute(text("REFRESH MATERIALIZED VIEW tiles.nature"))
        return LoadResult(rows=len(frame))


NATURE_NAME_FIELDS = (
    "naziv",
    "naziv_podrucja",
    "site_name",
    "sitename",
    "ime",
    "name",
    "naziv_hr",
    "site",
)
NATURE_CATEGORY_FIELDS = (
    "kategorija",
    "kategorija_zastite",
    "site_code",
    "sitecode",
    "tip",
    "category",
)
