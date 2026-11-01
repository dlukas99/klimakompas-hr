"""Read queries behind the API: card, JLS, rankings, warnings, air and nature (SPEC §12)."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import yaml
from pyproj import Transformer
from rasterio.windows import Window
from sqlalchemy import Connection, text

from klimakompas.core.config import ROOT, load_index_config, load_sources, load_thresholds
from klimakompas.live.parsers import eaqi_class
from klimakompas.pipeline.hazards import air_card_level, flood_card_level
from klimakompas.pipeline.static_layers import flood_paths

FLOOD_DIR = ROOT / "data" / "processed"
LEVEL_LABELS = load_index_config()["ikr"]["labels"]
POP_ROUND = 10
POLLUTANTS = {"pm25": "28", "pm10": "5", "no2": "1", "o3": "31"}
POLLUTANT_NAMES = {value: key for key, value in POLLUTANTS.items()}
EARTH_METRES_PER_DEGREE = 111_320.0
NATURE_RADIUS_M = 1000

_to_laea = Transformer.from_crs(4326, 3035, always_xy=True)


def cell_id_at(lat: float, lon: float) -> str:
    x, y = _to_laea.transform(lon, lat)
    return f"CRS3035RES1000mN{int(y // 1000) * 1000}E{int(x // 1000) * 1000}"


def _level_label(level: int | None) -> str | None:
    return LEVEL_LABELS[level - 1] if level else None


def sample_flood_depths(lat: float, lon: float, folder: Path = FLOOD_DIR) -> dict[str, Any]:
    """Depth at the point per return period, and whether RP100 lies within the near distance."""
    config = load_index_config()["hazards"]["flood"]
    near_m = float(config["card_levels"]["near_rp100_m"])
    depths: dict[int, float | None] = {}
    near = False
    available = True
    for return_period, path in flood_paths(folder, config["return_periods"]).items():
        if not path.exists():
            available = False
            depths[return_period] = None
            continue
        with rasterio.open(path) as dataset:
            value = next(dataset.sample([(lon, lat)]))[0]
            nodata = dataset.nodata
            depths[return_period] = (
                None if (nodata is not None and value == nodata) or value < 0 else float(value)
            )
            if return_period == 100:
                row, col = dataset.index(lon, lat)
                radius_y = int(near_m / EARTH_METRES_PER_DEGREE / abs(dataset.res[1])) + 1
                scale = np.cos(np.radians(lat))
                radius_x = int(near_m / (EARTH_METRES_PER_DEGREE * scale) / abs(dataset.res[0])) + 1
                window = Window(col - radius_x, row - radius_y, 2 * radius_x + 1, 2 * radius_y + 1)
                block = dataset.read(1, window=window, boundless=True, fill_value=nodata or -9999)
                near = bool((block > 0).any())
    return {"depths": depths, "near_rp100": near, "available": available}


@lru_cache
def load_advice() -> dict[str, dict[str, Any]]:
    result = {}
    for name in ("poplave", "toplina", "pozar", "zrak"):
        with (ROOT / "config" / "advice" / f"{name}.yaml").open(encoding="utf-8") as handle:
            result[name] = yaml.safe_load(handle)
    return result


CELL_SQL = text("""
SELECT c.cell_id, c.land_share, c.overlap_share,
       n.code AS naselje_code, n.name AS naselje_name,
       j.code AS jls_code, j.name AS jls_name, j.kind AS jls_kind,
       z.code AS zupanija_code, z.name AS zupanija_name,
       p.pop_total, p.share_ge65, p.share_lt15, p.age_share_source, p.suppressed,
       f.s_rp10, f.s_rp100, f.s_rp500, f.s_deep_rp100, f.h_flood,
       h.hot_days, h.tropical_nights, h.lst_median_c, h.lst_delta_c, h.tree_share, h.h_heat,
       x.fwi_days, x.fuel_share, x.burnt_years_2km, x.h_fire,
       a.pm25_annual, a.year AS pm25_year, a.h_air, a.gap_filled,
       r.ikr, r.ikr_class, r.v_gen, r.v_heat, r.v_imputed,
       r.r_flood, r.r_heat, r.r_fire, r.r_air,
       r.class_heat, r.class_fire,
       ru.index_version
FROM ref.grid_1km c
JOIN ref.naselja n ON n.code = c.naselje_code
JOIN ref.jls j ON j.code = c.jls_code
JOIN ref.zupanije z ON z.code = c.zupanija_code
LEFT JOIN pop.grid_2021 p USING (cell_id)
LEFT JOIN haz.flood_cell f USING (cell_id)
LEFT JOIN haz.heat_cell h USING (cell_id)
LEFT JOIN haz.fire_cell x USING (cell_id)
LEFT JOIN haz.air_cell a USING (cell_id)
LEFT JOIN idx.current_risk_cell r USING (cell_id)
LEFT JOIN idx.runs ru ON ru.run_id = r.run_id
WHERE c.cell_id = :cell_id
""")


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


def _explain(h: float | None, r: float | None, v: float | None) -> list[dict[str, Any]]:
    if h is None:
        return []
    items: list[dict[str, Any]] = [{"factor": "hazard", "value": round(h, 3)}]
    if v is not None:
        items.append({"factor": "vulnerability", "value": round(v, 3)})
    if r is not None:
        items.append({"factor": "risk", "value": round(r, 3)})
    return items


def _flood_block(row: Any, sampled: dict[str, Any], levels: dict[str, Any]) -> dict[str, Any]:
    depths = sampled["depths"]
    level = flood_card_level(
        depths.get(10), depths.get(100), depths.get(500), sampled["near_rp100"], levels
    )
    if (depths.get(10) or 0) > 0:
        zone = 10
    elif (depths.get(100) or 0) > 0:
        zone = 100
    elif (depths.get(500) or 0) > 0:
        zone = 500
    else:
        zone = None
    return {
        "level": level if sampled["available"] else None,
        "label": _level_label(level) if sampled["available"] else None,
        "h": _round(row.h_flood, 3),
        "r": _round(row.r_flood, 3),
        "key_value": {
            "zone_return_period": zone,
            "near_rp100": sampled["near_rp100"],
            "depth_rp100_m": _round(depths.get(100)),
            "cell_share_rp100": _round(row.s_rp100, 3),
        },
        "explanation": _explain(row.h_flood, row.r_flood, row.v_gen),
        "source_ids": ["jrc_efas_flood"],
    }


def _heat_block(row: Any) -> dict[str, Any]:
    return {
        "level": row.class_heat,
        "label": _level_label(row.class_heat),
        "h": _round(row.h_heat, 3),
        "r": _round(row.r_heat, 3),
        "key_value": {
            "hot_days": _round(row.hot_days),
            "tropical_nights": _round(row.tropical_nights),
            "lst_delta_c": _round(row.lst_delta_c),
            "tree_share": _round(row.tree_share, 3),
        },
        "explanation": _explain(row.h_heat, row.r_heat, row.v_heat),
        "source_ids": ["ecde", "landsat_lst", "esa_worldcover"],
    }


def _fire_block(row: Any) -> dict[str, Any]:
    return {
        "level": row.class_fire,
        "label": _level_label(row.class_fire),
        "h": _round(row.h_fire, 3),
        "r": _round(row.r_fire, 3),
        "key_value": {
            "fwi_days": _round(row.fwi_days),
            "fuel_share": _round(row.fuel_share, 3),
            "burnt_years_2km": row.burnt_years_2km,
        },
        "explanation": _explain(row.h_fire, row.r_fire, row.v_gen),
        "source_ids": ["ecde", "esa_worldcover", "burnt_areas"],
    }


def _air_block(row: Any, boundaries: list[float]) -> dict[str, Any]:
    level = air_card_level(row.pm25_annual, boundaries) if row.pm25_annual is not None else None
    return {
        "level": level,
        "label": _level_label(level),
        "h": _round(row.h_air, 3),
        "r": _round(row.r_air, 3),
        "key_value": {
            "pm25_annual": _round(row.pm25_annual),
            "year": row.pm25_year,
            "who_guideline": boundaries[0],
            "gap_filled": row.gap_filled,
        },
        "explanation": _explain(row.h_air, row.r_air, row.v_gen),
        "source_ids": ["eea_pm25_1km"],
    }


def _rounded_population(total: int | None) -> dict[str, Any]:
    if total is None or total <= 0:
        return {"total_rounded": 0, "below_threshold": False}
    if total < POP_ROUND:
        return {"total_rounded": None, "below_threshold": True}
    return {
        "total_rounded": int(round(total / POP_ROUND) * POP_ROUND),
        "below_threshold": False,
    }


def _percentile(conn: Connection, ikr: float | None) -> float | None:
    if ikr is None:
        return None
    row = conn.execute(
        text(
            "SELECT count(*) FILTER (WHERE ikr < :ikr) AS below, count(ikr) AS total "
            "FROM idx.current_risk_cell"
        ),
        {"ikr": ikr},
    ).one()
    return round(100 * row.below / row.total, 1) if row.total else None


def active_warnings(conn: Connection, zupanija_code: str | None = None) -> list[dict[str, Any]]:
    """Warnings not yet expired. Without a county, all land and sea warnings."""
    rows = conn.execute(
        text(
            """
            SELECT id, event, awareness_type, level, level_name, severity, onset, expires,
                   area_desc, zupanija_code, description, instruction, fetched_at
            FROM live.warnings
            WHERE (expires IS NULL OR expires > now())
              AND (CAST(:zupanija AS text) IS NULL OR zupanija_code = :zupanija)
            ORDER BY level DESC NULLS LAST, onset
            """
        ),
        {"zupanija": zupanija_code},
    ).mappings()
    return [dict(row) for row in rows]


def source_status(conn: Connection, source_id: str) -> Any:
    return conn.execute(
        text("SELECT last_success_at, last_status FROM meta.sources WHERE source_id = :id"),
        {"id": source_id},
    ).one_or_none()


def station_latest(conn: Connection) -> list[dict[str, Any]]:
    """Latest value of each pollutant at each station, with the EAQI class per pollutant."""
    thresholds = load_thresholds()
    bands = thresholds["eaqi"]["bands"]
    labels = thresholds["eaqi"]["labels"]
    stale = datetime.now(UTC) - timedelta(hours=thresholds["stale_after_hours"])
    rows = conn.execute(
        text(
            """
            SELECT s.station_id, s.name, s.network,
                   ST_Y(ST_Transform(s.geom, 4326)) AS lat, ST_X(ST_Transform(s.geom, 4326)) AS lon,
                   o.pollutant_id, o.ts, o.value, o.unit
            FROM live.aq_stations s
            JOIN LATERAL (
                SELECT DISTINCT ON (pollutant_id) pollutant_id, ts, value, unit
                FROM live.aq_obs o WHERE o.station_id = s.station_id
                ORDER BY pollutant_id, ts DESC
            ) o ON true
            WHERE s.geom IS NOT NULL
            """
        )
    )
    stations: dict[str, dict[str, Any]] = {}
    for row in rows:
        station = stations.setdefault(
            row.station_id,
            {
                "id": row.station_id,
                "name": row.name,
                "network": row.network,
                "lat": row.lat,
                "lon": row.lon,
                "values": {},
                "eaqi_class": None,
                "eaqi_label": None,
                "observed_at": None,
                "stale": True,
            },
        )
        name = POLLUTANT_NAMES.get(row.pollutant_id)
        if not name:
            continue
        fresh = row.ts >= stale
        klass = eaqi_class(row.value, bands[name])
        station["values"][name] = {
            "value": round(row.value, 1),
            "unit": row.unit,
            "observed_at": row.ts,
            "stale": not fresh,
            "eaqi_class": klass,
            "eaqi_label": labels[klass - 1],
        }
        if station["observed_at"] is None or row.ts > station["observed_at"]:
            station["observed_at"] = row.ts
        if fresh:
            station["stale"] = False
            if station["eaqi_class"] is None or klass > station["eaqi_class"]:
                station["eaqi_class"] = klass
                station["eaqi_label"] = labels[klass - 1]
    return list(stations.values())


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    x1, y1 = _to_laea.transform(lon1, lat1)
    x2, y2 = _to_laea.transform(lon2, lat2)
    return float(np.hypot(x1 - x2, y1 - y2) / 1000)


def choose_air_now(
    stations: list[dict[str, Any]], lat: float, lon: float, local_km: float
) -> dict[str, Any] | None:
    """ADR 0004: the local station's PM2.5, then its PM10, then the nearest fresh PM2.5.

    Other pollutants at the station chosen are shown too; PM10 never stands in for PM2.5.
    """
    ranked = sorted(
        (
            (_distance_km(lat, lon, station["lat"], station["lon"]), station)
            for station in stations
            if station["lat"] is not None and station["lon"] is not None
        ),
        key=lambda item: item[0],
    )

    def fresh(station: dict[str, Any], pollutant: str) -> bool:
        value = station["values"].get(pollutant)
        return value is not None and not value["stale"]

    local = [item for item in ranked if item[0] <= local_km]
    for distance, station in local:
        if fresh(station, "pm25"):
            return _air_now(station, distance, "pm25", "local")
    for distance, station in local:
        if fresh(station, "pm10"):
            return _air_now(station, distance, "pm10", "local_pm10")
    for distance, station in ranked:
        if fresh(station, "pm25"):
            return _air_now(station, distance, "pm25", "nearest_pm25")
    return None


def _air_now(
    station: dict[str, Any], distance: float, pollutant: str, substitution: str
) -> dict[str, Any]:
    return {
        "station": {
            "id": station["id"],
            "name": station["name"],
            "distance_km": round(distance, 1),
        },
        "pollutant": pollutant,
        "substitution": substitution,
        "value": station["values"][pollutant],
        "values": station["values"],
        "observed_at": station["values"][pollutant]["observed_at"],
    }


def nature_nearby(conn: Connection, lat: float, lon: float, radius_m: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            WITH p AS (SELECT ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 3035) AS g)
            SELECT DISTINCT ON (a.name, a.layer) a.layer, a.name, a.category,
                   round(ST_Distance(a.geom, p.g)) AS distance_m
            FROM live.nature_areas a, p
            WHERE ST_DWithin(a.geom, p.g, :radius)
            ORDER BY a.name, a.layer, distance_m
            """
        ),
        {"lat": lat, "lon": lon, "radius": radius_m},
    ).mappings()
    return sorted((dict(row) for row in rows), key=lambda item: item["distance_m"])


def latest_forecast(conn: Connection, station_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT target_ts AS target_time, yhat AS pm25, lo, hi, model_version
            FROM ml.pm25_forecast
            WHERE station_id = :id
              AND issued_at = (SELECT max(issued_at) FROM ml.pm25_forecast WHERE station_id = :id)
              AND issued_at > now() - interval '6 hours'
            ORDER BY target_ts
            """
        ),
        {"id": station_id},
    ).mappings()
    return [dict(row) for row in rows]


def fire_index_near(conn: Connection, lat: float, lon: float) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
            WITH p AS (SELECT ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 3035) AS g)
            SELECT f.station_name, f.fwi, f.category, f.index_date, f.in_season, f.fetched_at,
                   round((ST_Distance(f.geom, p.g) / 1000)::numeric, 1) AS distance_km
            FROM live.fire_index f, p WHERE f.geom IS NOT NULL
            ORDER BY f.geom <-> p.g LIMIT 1
            """
            ),
            {"lat": lat, "lon": lon},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def heatwave_state(conn: Connection) -> dict[str, Any] | None:
    row = (
        conn.execute(text("SELECT level, raw, fetched_at FROM live.heatwave WHERE id = 'current'"))
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def build_card(
    conn: Connection,
    lat: float,
    lon: float,
    flood_folder: Path = FLOOD_DIR,
    label: str | None = None,
) -> dict[str, Any] | None:
    """The climate card for a point. Live parts that fail only mark the card as partial."""
    config = load_index_config()
    thresholds = load_thresholds()
    cell_id = cell_id_at(lat, lon)
    row = conn.execute(CELL_SQL, {"cell_id": cell_id}).one_or_none()
    if row is None:
        return None

    sampled = sample_flood_depths(lat, lon, flood_folder)
    degraded: list[str] = []
    warnings_status = source_status(conn, "dhmz_cap")
    if warnings_status is None or warnings_status.last_status != "success":
        degraded.append("dhmz_cap")
    stations = station_latest(conn)
    air_now = choose_air_now(stations, lat, lon, float(thresholds.get("air_local_km", 15)))
    if air_now is None:
        degraded.append("azo_aq_rest")

    forecast = latest_forecast(conn, air_now["station"]["id"]) if air_now else []
    return {
        "location": {
            "lat": lat,
            "lon": lon,
            "label": label or row.naselje_name,
            "naselje": {"code": row.naselje_code, "name": row.naselje_name},
            "jls": {"code": row.jls_code, "name": row.jls_name, "kind": row.jls_kind},
            "zupanija": {"code": row.zupanija_code, "name": row.zupanija_name},
            "cell_id": row.cell_id,
        },
        "ikr": {
            "value": _round(row.ikr, 3),
            "level": row.ikr_class,
            "label": _level_label(row.ikr_class),
            "percentile": _percentile(conn, row.ikr),
            "index_version": row.index_version,
            "populated": row.ikr is not None,
        },
        "hazards": {
            "flood": _flood_block(row, sampled, config["hazards"]["flood"]["card_levels"]),
            "heat": _heat_block(row),
            "fire": _fire_block(row),
            "air": _air_block(row, thresholds["pm25_annual_ugm3"]["card_levels"]),
        },
        "population": {
            **_rounded_population(row.pop_total),
            "share_65plus": _round(row.share_ge65, 3),
            "share_under15": _round(row.share_lt15, 3),
            "age_share_source": row.age_share_source,
            "suppressed": bool(row.suppressed),
        },
        "live": {
            "warnings": active_warnings(conn, row.zupanija_code),
            "warnings_checked_at": warnings_status.last_success_at if warnings_status else None,
            "air_now": air_now,
            "air_forecast": forecast,
            "fire_index": fire_index_near(conn, lat, lon),
            "heatwave": heatwave_state(conn),
            "nature_nearby": nature_nearby(conn, lat, lon, NATURE_RADIUS_M),
        },
        "advice": load_advice(),
        "generated_at": datetime.now(UTC),
        "partial": bool(degraded),
        "degraded_sources": degraded,
    }


JLS_SQL = """
SELECT j.code, j.name, j.kind, z.code AS zupanija_code, z.name AS zupanija_name,
       r.pop, r.pop65, r.ikr_popw, r.ikr_class, r.exposed, r.rank_hr, r.rank_zup,
       (SELECT count(*) FROM idx.current_risk_jls) AS total_hr,
       (SELECT count(*) FROM idx.current_risk_jls r2 JOIN ref.jls j2 ON j2.code = r2.jls_code
        WHERE j2.zupanija_code = j.zupanija_code) AS total_zup,
       ST_Y(ST_Transform(ST_PointOnSurface(j.geom), 4326)) AS lat,
       ST_X(ST_Transform(ST_PointOnSurface(j.geom), 4326)) AS lon,
       ST_XMin(b.box) AS west, ST_YMin(b.box) AS south, ST_XMax(b.box) AS east,
       ST_YMax(b.box) AS north,
       (SELECT index_version FROM idx.runs ORDER BY run_id DESC LIMIT 1) AS index_version
FROM ref.jls j
JOIN ref.zupanije z ON z.code = j.zupanija_code
LEFT JOIN idx.current_risk_jls r ON r.jls_code = j.code
CROSS JOIN LATERAL (SELECT ST_Envelope(ST_Transform(j.geom, 4326)) AS box) b
"""


def list_jls(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT j.code, j.name, j.kind, z.name AS zupanija_name, r.pop, r.ikr_popw,
                   r.ikr_class, r.rank_hr
            FROM ref.jls j
            JOIN ref.zupanije z ON z.code = j.zupanija_code
            LEFT JOIN idx.current_risk_jls r ON r.jls_code = j.code
            ORDER BY j.name
            """
        )
    ).mappings()
    return [dict(row) for row in rows]


def _hazard_profile(
    conn: Connection, where: str, params: dict[str, Any]
) -> dict[str, float | None]:
    row = (
        conn.execute(
            text(
                f"""
            SELECT sum(r.pop_total * r.r_flood) / sum(r.pop_total) AS flood,
                   sum(r.pop_total * r.r_heat) / sum(r.pop_total) AS heat,
                   sum(r.pop_total * r.r_fire) / sum(r.pop_total) AS fire,
                   sum(r.pop_total * r.r_air) / sum(r.pop_total) AS air
            FROM idx.current_risk_cell r
            JOIN ref.grid_1km c USING (cell_id)
            WHERE {where}
            """
            ),
            params,
        )
        .mappings()
        .one()
    )
    return {key: _round(value, 3) for key, value in row.items()}


def attention_rules(row: Any) -> list[dict[str, Any]]:
    """Suggestions from config, worded as things to consider (SPEC §9.3)."""
    rules = load_thresholds().get("jls_attention", [])
    exposed = row.exposed or {}
    result = []
    for rule in rules:
        hazard = exposed.get(rule["hazard"], {})
        value = hazard.get(rule["metric"], 0)
        if value >= rule["min"]:
            result.append(
                {
                    "hazard": rule["hazard"],
                    "text": rule["text"],
                    "value": round(value),
                    "url": rule.get("url"),
                }
            )
    return result


def jls_detail(conn: Connection, code: str) -> dict[str, Any] | None:
    row = conn.execute(text(f"{JLS_SQL} WHERE j.code = :code"), {"code": code}).one_or_none()
    if row is None:
        return None
    return {
        "code": row.code,
        "name": row.name,
        "kind": row.kind,
        "zupanija": {"code": row.zupanija_code, "name": row.zupanija_name},
        "pop": row.pop,
        "pop65": row.pop65,
        "ikr": _round(row.ikr_popw, 3),
        "ikr_class": row.ikr_class,
        "ikr_label": _level_label(row.ikr_class),
        "rank_hr": row.rank_hr,
        "rank_zup": row.rank_zup,
        "total_hr": row.total_hr,
        "total_zup": row.total_zup,
        "exposed": row.exposed or {},
        "lat": row.lat,
        "lon": row.lon,
        "bbox": (row.west, row.south, row.east, row.north),
        "index_version": row.index_version,
        "profile": {
            "jls": _hazard_profile(conn, "c.jls_code = :code", {"code": code}),
            "zupanija": _hazard_profile(
                conn, "c.zupanija_code = :zupanija", {"zupanija": row.zupanija_code}
            ),
            "hr": _hazard_profile(conn, "true", {}),
        },
        "attention": attention_rules(row),
    }


def jls_naselja(conn: Connection, code: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT n.code, n.name, p.pop_total AS pop, r.ikr_popw AS ikr, r.ikr_class,
                   r.exposed
            FROM ref.naselja n
            LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code
            LEFT JOIN idx.current_risk_naselja r ON r.naselje_code = n.code
            WHERE n.jls_code = :code
            ORDER BY r.ikr_popw DESC NULLS LAST, n.name
            """
        ),
        {"code": code},
    ).mappings()
    return [dict(row) for row in rows]


def jls_cells(conn: Connection, code: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT r.cell_id, r.pop_total, r.ikr, r.ikr_class, r.class_flood, r.class_heat,
                   r.class_fire, r.class_air, n.name AS naselje
            FROM idx.current_risk_cell r
            JOIN ref.grid_1km c USING (cell_id)
            JOIN ref.naselja n ON n.code = c.naselje_code
            WHERE c.jls_code = :code
            ORDER BY r.ikr DESC NULLS LAST
            """
        ),
        {"code": code},
    ).mappings()
    return [
        {**dict(row), "pop_total": row["pop_total"] if row["pop_total"] >= POP_ROUND else None}
        for row in rows
    ]


RANKING_METRICS = {
    "ikr": "r.ikr_popw",
    "exposed": "(r.exposed->:hazard->>'pop')::float",
    "exposed_share": "(r.exposed->:hazard->>'share')::float",
}


def rankings(
    conn: Connection, hazard: str | None, metric: str, zupanija: str | None, limit: int
) -> list[dict[str, Any]]:
    expression = RANKING_METRICS[metric]
    params: dict[str, Any] = {"zupanija": zupanija, "limit": limit}
    if metric != "ikr":
        params["hazard"] = hazard
    rows = conn.execute(
        text(
            f"""
            SELECT j.code, j.name, j.kind, z.name AS zupanija_name, r.pop, r.ikr_popw AS ikr,
                   r.ikr_class, r.rank_hr, r.rank_zup, {expression} AS value
            FROM idx.current_risk_jls r
            JOIN ref.jls j ON j.code = r.jls_code
            JOIN ref.zupanije z ON z.code = j.zupanija_code
            WHERE (CAST(:zupanija AS text) IS NULL OR j.zupanija_code = :zupanija)
            ORDER BY value DESC NULLS LAST, j.name
            LIMIT :limit
            """
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def station_series(
    conn: Connection, station_id: str, pollutant: str, hours: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT ts, value, unit FROM live.aq_obs
            WHERE station_id = :id AND pollutant_id = :pollutant
              AND ts > now() - make_interval(hours => :hours)
            ORDER BY ts
            """
        ),
        {"id": station_id, "pollutant": POLLUTANTS[pollutant], "hours": hours},
    ).mappings()
    return [dict(row) for row in rows]


def _source_state(source: Any, row: Any, now: datetime) -> str:
    """Green, yellow or red for /podaci. Browser-only sources are never called by the server."""
    if source.access.get("type") in {"wms_browser_only", "browser_style"}:
        return "browser"
    if row is None or row.last_status is None:
        return "unused"
    if row.last_status != "success":
        return "failed"
    if not source.stale_after:
        return "static"
    if row.last_success_at and now - row.last_success_at > _iso_duration(source.stale_after):
        return "stale"
    return "ok"


def _iso_duration(value: str) -> timedelta:
    """The only forms used in sources.yaml: PT6H and P3D."""
    number = int(value.strip("PTHD"))
    return timedelta(hours=number) if value.endswith("H") else timedelta(days=number)


def list_sources(conn: Connection) -> list[dict[str, Any]]:
    status = {
        row.source_id: row
        for row in conn.execute(
            text("SELECT source_id, last_success_at, last_status FROM meta.sources")
        )
    }
    portal = {
        row.source_id: row
        for row in conn.execute(
            text(
                "SELECT source_id, title, license_title, metadata_modified FROM meta.ckan_metadata"
            )
        )
    }
    now = datetime.now(UTC)
    result = []
    for source in load_sources():
        row = status.get(source.id)
        record = portal.get(source.id)
        result.append(
            {
                "id": source.id,
                "name": source.name,
                "publisher": source.publisher,
                "license": source.license,
                "attribution": source.attribution,
                "landing_url": source.landing_url,
                "priority": source.priority,
                "verified_on": source.verification.date,
                "used_for": source.used_for,
                "schedule": source.schedule,
                "stale_after": source.stale_after,
                "last_success_at": row.last_success_at if row else None,
                "last_status": row.last_status if row else None,
                "state": _source_state(source, row, now),
                "portal_title": record.title if record else None,
                "portal_license": record.license_title if record else None,
                "portal_modified": record.metadata_modified if record else None,
            }
        )
    return result
