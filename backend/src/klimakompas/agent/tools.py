"""Read-only tools of the assistant (SPEC §10.2). Each returns data, sources and a timestamp."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import Connection, text

from klimakompas.api import data
from klimakompas.api.geocode import geocode
from klimakompas.core.config import get_settings, load_sources

RANK_LIMIT = 20
HAZARD_COLUMNS = {
    "ikr": "ikr",
    "flood": "r_flood",
    "heat": "r_heat",
    "fire": "r_fire",
    "air": "r_air",
}
SEARCH_TIMEOUT_S = 8.0
HAZARD_NAMES_HR = {"flood": "poplave", "heat": "toplina", "fire": "pozar", "air": "zrak"}


def _sources(conn: Connection, ids: list[str]) -> list[dict[str, Any]]:
    registry = {source.id: source for source in load_sources()}
    modified = {
        row.source_id: row.last_success_at
        for row in conn.execute(text("SELECT source_id, last_success_at FROM meta.sources"))
    }
    result = []
    for source_id in ids:
        source = registry[source_id]
        last = modified.get(source_id)
        result.append(
            {
                "id": source_id,
                "title": source.name,
                "publisher": source.publisher,
                "url": source.landing_url,
                "last_modified": last.isoformat() if last else None,
            }
        )
    return result


def _result(conn: Connection, payload: Any, source_ids: list[str]) -> dict[str, Any]:
    return {
        "data": payload,
        "sources": _sources(conn, source_ids),
        "as_of": datetime.now(UTC).isoformat(),
    }


def tool_geocode(conn: Connection, query: str) -> dict[str, Any]:
    results = geocode(conn, query, 5).results
    return _result(
        conn,
        [item.model_dump(exclude={"bbox"}) for item in results],
        ["dgu_ad", "dgu_au"],
    )


def tool_place_card(conn: Connection, lat: float, lon: float) -> dict[str, Any]:
    card = data.build_card(conn, lat, lon)
    if card is None:
        return _result(conn, {"error": "Lokacija je izvan područja Hrvatske."}, ["dgu_au"])
    air = card["live"]["air_now"]
    location = card["location"]
    summary = {
        "mjesto": location["label"],
        "opcina_ili_grad": location["jls"]["name"],
        "zupanija": location["zupanija"]["name"],
        "lat": location["lat"],
        "lon": location["lon"],
        "ukupni_rizik": {
            "label": card["ikr"]["label"],
            "veci_od_postotka_naseljenih_podrucja": card["ikr"]["percentile"],
        },
        "opasnosti": {
            HAZARD_NAMES_HR[name]: {"label": block["label"], "vrijednosti": block["key_value"]}
            for name, block in card["hazards"].items()
        },
        "upozorenja": [
            {"dogadaj": item["event"], "od": item["onset"], "do": item["expires"]}
            for item in card["live"]["warnings"]
        ],
        "zrak_sada": (
            {
                "postaja": air["station"]["name"],
                "udaljenost_km": air["station"]["distance_km"],
                "tvar": air["pollutant"],
                "shown_instead_of_local_pm25": air["substitution"] != "local",
                "vrijednost": air["value"]["value"],
                "razina": air["value"]["eaqi_label"],
            }
            if air
            else None
        ),
    }
    return _result(
        conn,
        summary,
        [
            "jrc_efas_flood",
            "ecde",
            "landsat_lst",
            "esa_worldcover",
            "burnt_areas",
            "eea_pm25_1km",
            "estat_census_grid_2021",
            "dhmz_cap",
            "azo_aq_rest",
        ],
    )


def _find_jls(conn: Connection, jls: str) -> str | None:
    if jls.isdigit():
        return jls
    code: str | None = conn.execute(
        text(
            """
            SELECT code FROM ref.jls, (SELECT ref.normalize_search(:name) AS value) q
            WHERE search_text % q.value OR starts_with(search_text, q.value)
            ORDER BY search_text = q.value DESC, similarity(search_text, q.value) DESC LIMIT 1
            """
        ),
        {"name": jls},
    ).scalar_one_or_none()
    return code


def tool_jls_profile(conn: Connection, jls: str) -> dict[str, Any]:
    code = _find_jls(conn, jls)
    detail = data.jls_detail(conn, code) if code else None
    if detail is None:
        return _result(conn, {"error": f"Nije pronađena općina ili grad: {jls}"}, ["dgu_au"])
    payload = {
        "name": detail["name"],
        "zupanija": detail["zupanija"]["name"],
        "stanovnika": detail["pop"],
        "stanovnika_65_plus": detail["pop65"],
        "label": detail["ikr_label"],
        "rang_u_hrvatskoj": detail["rank_hr"],
        "od_ukupno": detail["total_hr"],
        "rang_u_zupaniji": detail["rank_zup"],
        "osobe_u_podrucjima_visokog_rizika": {
            HAZARD_NAMES_HR[name]: {
                "osobe": round(values["pop"]),
                "osobe_65_plus": round(values["pop65"]),
            }
            for name, values in detail["exposed"].items()
        },
        "lat": detail["lat"],
        "lon": detail["lon"],
    }
    return _result(conn, payload, ["dzs_naselja_2021", "estat_census_grid_2021", "dgu_au"])


def _hazard_sources(hazard: str) -> list[str]:
    by_hazard = {
        "flood": ["jrc_efas_flood"],
        "heat": ["ecde", "landsat_lst", "esa_worldcover", "dhmz_climate"],
        "fire": ["ecde", "esa_worldcover", "burnt_areas"],
        "air": ["eea_pm25_1km"],
    }
    return [*by_hazard.get(hazard, ["jrc_efas_flood", "ecde", "eea_pm25_1km"]), "dzs_naselja_2021"]


def tool_rank_areas(
    conn: Connection,
    level: str = "jls",
    hazard: str = "ikr",
    metric: str = "risk",
    zupanija: str | None = None,
    jls: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), RANK_LIMIT))
    if hazard not in HAZARD_COLUMNS:
        return _result(conn, {"error": f"Nepoznata opasnost: {hazard}"}, ["dgu_au"])
    jls_code = _find_jls(conn, jls) if jls else None
    zupanija_like = f"%{zupanija}%" if zupanija else None
    params = {"jls": jls_code, "zupanija": zupanija_like, "limit": limit}
    filters = (
        "(CAST(:zupanija AS text) IS NULL OR z.name ILIKE :zupanija) "
        "AND (CAST(:jls AS text) IS NULL OR j.code = :jls)"
    )
    if level == "cells":
        column = HAZARD_COLUMNS[hazard]
        rows = conn.execute(
            text(
                f"""
                SELECT r.cell_id, n.name AS naselje, j.name AS jls, r.{column} AS value
                FROM idx.current_risk_cell r
                JOIN ref.grid_1km c USING (cell_id)
                JOIN ref.naselja n ON n.code = c.naselje_code
                JOIN ref.jls j ON j.code = c.jls_code
                JOIN ref.zupanije z ON z.code = j.zupanija_code
                WHERE {filters} AND r.{column} IS NOT NULL
                ORDER BY value DESC LIMIT :limit
                """
            ),
            params,
        ).mappings()
        return _result(conn, [dict(row) for row in rows], _hazard_sources(hazard))

    table = "idx.current_risk_naselja" if level == "naselja" else "idx.current_risk_jls"
    if metric in {"pop_exposed", "pop65_exposed"}:
        if hazard == "ikr":
            return _result(conn, {"error": "Izloženost se računa po pojedinoj opasnosti."}, [])
        field = "pop65" if metric == "pop65_exposed" else "pop"
        value = f"(r.exposed->'{hazard}'->>'{field}')::float"
    elif hazard == "ikr":
        value = "r.ikr_popw"
    else:
        # Risk of one hazard for an area: population-weighted mean of its cells.
        column = HAZARD_COLUMNS[hazard]
        code_column = "c.naselje_code" if level == "naselja" else "c.jls_code"
        key = "r.naselje_code" if level == "naselja" else "r.jls_code"
        value = (
            f"(SELECT sum(x.pop_total * x.{column}) / nullif(sum(x.pop_total), 0) "
            f"FROM idx.current_risk_cell x JOIN ref.grid_1km c USING (cell_id) "
            f"WHERE {code_column} = {key})"
        )
    if level == "naselja":
        sql = f"""
            SELECT n.name AS naselje, j.name AS jls, {value} AS value
            FROM {table} r
            JOIN ref.naselja n ON n.code = r.naselje_code
            JOIN ref.jls j ON j.code = n.jls_code
            JOIN ref.zupanije z ON z.code = j.zupanija_code
            WHERE {filters}
            ORDER BY value DESC NULLS LAST LIMIT :limit
        """
    else:
        sql = f"""
            SELECT j.code, j.name, z.name AS zupanija, r.pop, r.rank_hr, {value} AS value
            FROM {table} r
            JOIN ref.jls j ON j.code = r.jls_code
            JOIN ref.zupanije z ON z.code = j.zupanija_code
            WHERE {filters}
            ORDER BY value DESC NULLS LAST LIMIT :limit
        """
    rows = conn.execute(text(sql), params).mappings()
    return _result(conn, [dict(row) for row in rows], _hazard_sources(hazard))


def tool_active_warnings(
    conn: Connection, region: str | None = None, lat: float | None = None, lon: float | None = None
) -> dict[str, Any]:
    code: str | None = None
    if lat is not None and lon is not None:
        code = conn.execute(
            text("SELECT zupanija_code FROM ref.grid_1km WHERE cell_id = :id"),
            {"id": data.cell_id_at(lat, lon)},
        ).scalar_one_or_none()
    elif region:
        code = conn.execute(
            text("SELECT code FROM ref.zupanije WHERE name ILIKE :name LIMIT 1"),
            {"name": f"%{region}%"},
        ).scalar_one_or_none()
    warnings = data.active_warnings(conn, code)
    payload = [
        {
            "event": item["event"],
            "area": item["area_desc"],
            "onset": item["onset"],
            "expires": item["expires"],
            "description": item["description"],
        }
        for item in warnings
    ]
    return _result(conn, payload, ["dhmz_cap"])


def tool_air_quality(
    conn: Connection, station: str | None = None, lat: float | None = None, lon: float | None = None
) -> dict[str, Any]:
    stations = data.station_latest(conn)
    if station:
        needle = station.casefold()
        match = [item for item in stations if needle in item["name"].casefold()]
        return _result(
            conn, match[:3] or {"error": f"Nije pronađena postaja: {station}"}, ["azo_aq_rest"]
        )
    if lat is not None and lon is not None:
        air = data.choose_air_now(stations, lat, lon, 15.0)
        if air is None:
            return _result(conn, {"error": "Nema svježih mjerenja u blizini."}, ["azo_aq_rest"])
        forecast = data.latest_forecast(conn, air["station"]["id"])
        return _result(conn, {**air, "forecast": forecast}, ["azo_aq_rest"])
    return _result(conn, {"error": "Navedite postaju ili lokaciju."}, ["azo_aq_rest"])


def tool_search_open_data(conn: Connection, query: str) -> dict[str, Any]:
    """Asks the Portal directly; the search words go to data.gov.hr and are not stored here."""
    source = next(item for item in load_sources() if item.id == "ckan")
    try:
        response = httpx.get(
            source.access["package_search"],
            params={"q": query, "rows": 5},
            headers={"User-Agent": get_settings().kk_user_agent},
            timeout=SEARCH_TIMEOUT_S,
        )
        response.raise_for_status()
        body = response.json()["result"]
    except (httpx.HTTPError, ValueError, KeyError):
        return _result(conn, {"error": "Portal otvorenih podataka trenutno nije dostupan."}, [])
    payload = {
        "count": body["count"],
        "results": [
            {
                "title": item.get("title"),
                "publisher": (item.get("organization") or {}).get("title"),
                "url": f"https://data.gov.hr/ckan/dataset/{item.get('name')}",
                "last_modified": item.get("metadata_modified"),
            }
            for item in body["results"]
        ],
    }
    return _result(conn, payload, ["ckan"])


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "geocode": tool_geocode,
    "get_place_card": tool_place_card,
    "get_jls_profile": tool_jls_profile,
    "rank_areas": tool_rank_areas,
    "get_active_warnings": tool_active_warnings,
    "get_air_quality": tool_air_quality,
    "search_open_data": tool_search_open_data,
}


def _function(name: str, description: str, properties: dict[str, Any], required: list[str]) -> Any:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


NUMBER_TYPE = {"type": "number"}
STRING_TYPE = {"type": "string"}

TOOL_SCHEMAS = [
    _function(
        "geocode",
        "Pronađi adresu, naselje ili općinu i vrati koordinate.",
        {"query": STRING_TYPE},
        ["query"],
    ),
    _function(
        "get_place_card",
        "Sažetak klimatske iskaznice za točku: rizici, stanovništvo, upozorenja, zrak.",
        {"lat": NUMBER_TYPE, "lon": NUMBER_TYPE},
        ["lat", "lon"],
    ),
    _function(
        "get_jls_profile",
        "Podaci o općini ili gradu: stanovništvo, IKR, rang, izloženi stanovnici.",
        {"jls": {"type": "string", "description": "Naziv ili šifra općine ili grada"}},
        ["jls"],
    ),
    _function(
        "rank_areas",
        "Rang-lista područja po riziku ili broju izloženih stanovnika.",
        {
            "level": {"type": "string", "enum": ["jls", "naselja", "cells"]},
            "hazard": {"type": "string", "enum": list(HAZARD_COLUMNS)},
            "metric": {"type": "string", "enum": ["risk", "pop_exposed", "pop65_exposed"]},
            "zupanija": STRING_TYPE,
            "jls": STRING_TYPE,
            "limit": {"type": "integer", "maximum": RANK_LIMIT},
        },
        [],
    ),
    _function(
        "get_active_warnings",
        "Aktivna upozorenja DHMZ-a za županiju ili točku.",
        {"region": STRING_TYPE, "lat": NUMBER_TYPE, "lon": NUMBER_TYPE},
        [],
    ),
    _function(
        "get_air_quality",
        "Zadnja mjerenja kvalitete zraka za postaju ili najbližu postaju točki, s prognozom.",
        {"station": STRING_TYPE, "lat": NUMBER_TYPE, "lon": NUMBER_TYPE},
        [],
    ),
    _function(
        "search_open_data",
        "Pretraži skupove na Portalu otvorenih podataka (data.gov.hr).",
        {"query": STRING_TYPE},
        ["query"],
    ),
]


def run_tool(conn: Connection, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Nepoznat alat: {name}", "sources": [], "data": None}
    try:
        return tool(conn, **arguments)
    except TypeError:
        return {"error": f"Neispravni argumenti za {name}", "sources": [], "data": None}


def to_tool_message(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)
