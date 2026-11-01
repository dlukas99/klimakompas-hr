"""Local geocoder over DGU addresses, settlements and JLS (SPEC §9.7).

Queries are never stored or logged. Run the server without access logs: the query is in the URL.
"""

import json
import re
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from klimakompas.api.schemas import GeocodeResponse, GeocodeResult

ADDRESS_TIMEOUT_MS = 1500
ADDRESS_CANDIDATES = 200
MIN_TOKEN_LENGTH_FOR_INDEX = 3

AREAS_SQL = text("""
WITH q AS (SELECT ref.normalize_search(:query) AS value),
areas AS (
    SELECT 'settlement' AS kind, n.code, n.name AS label, j.name AS detail, n.search_text,
           n.point AS location, n.geom, p.pop_total AS population
    FROM ref.naselja n
    JOIN ref.jls j ON j.code = n.jls_code
    LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code, q
    WHERE n.search_text % q.value OR starts_with(n.search_text, q.value)
    UNION ALL
    SELECT 'municipality', j.code, j.name,
           (CASE j.kind WHEN 'grad' THEN 'Grad' WHEN 'opcina' THEN 'Općina' END) || ', ' || z.name,
           j.search_text, ST_PointOnSurface(j.geom), j.geom, p.pop_total
    FROM ref.jls j
    JOIN ref.zupanije z ON z.code = j.zupanija_code
    LEFT JOIN pop.jls_2021 p ON p.jls_code = j.code, q
    WHERE j.search_text % q.value OR starts_with(j.search_text, q.value)
), ranked AS (
    SELECT a.*, a.search_text = q.value AS exact, similarity(a.search_text, q.value) AS score
    FROM areas a, q
    ORDER BY exact DESC, score DESC, population DESC NULLS LAST, kind
    LIMIT :limit
)
SELECT kind, code, label, detail, population, score, exact,
       ST_Y(ST_Transform(location, 4326)) AS lat, ST_X(ST_Transform(location, 4326)) AS lon,
       ST_AsGeoJSON(ST_Envelope(ST_Transform(geom, 4326))) AS envelope
FROM ranked
""")

ADDRESSES_SQL = text("""
WITH candidates AS (
    SELECT a.id, a.label, a.jls_code, a.geom, a.search_text
    FROM ref.addresses a
    WHERE a.search_text LIKE ALL (:patterns)
    LIMIT :candidates
)
SELECT c.label, j.name AS detail, ST_Y(ST_Transform(c.geom, 4326)) AS lat,
       ST_X(ST_Transform(c.geom, 4326)) AS lon,
       similarity(c.search_text, ref.normalize_search(:query)) AS score
FROM candidates c
LEFT JOIN ref.jls j ON j.code = c.jls_code
ORDER BY score DESC, c.label
LIMIT :limit
""")


def _tokens(query: str) -> list[str]:
    return [token for token in re.split(r"[\s,]+", query.strip()) if token]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _bbox(envelope: str) -> tuple[float, float, float, float] | None:
    geometry: dict[str, Any] = json.loads(envelope)
    if geometry["type"] != "Polygon":
        return None
    longitudes = [point[0] for point in geometry["coordinates"][0]]
    latitudes = [point[1] for point in geometry["coordinates"][0]]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def _search_addresses(conn: Connection, query: str, limit: int) -> list[GeocodeResult] | None:
    """Return matches, or None if the search timed out. Only names remain in that case."""
    tokens = _tokens(query)
    # A trigram index needs at least one token of three characters to narrow the search.
    if not any(len(token) >= MIN_TOKEN_LENGTH_FOR_INDEX for token in tokens):
        return None
    normalized = conn.execute(
        text("SELECT ref.normalize_search(:value)"), {"value": " ".join(tokens)}
    ).scalar_one()
    patterns = [f"%{_escape_like(token)}%" for token in normalized.split(" ")]
    try:
        with conn.begin_nested():
            conn.execute(text(f"SET LOCAL statement_timeout = {ADDRESS_TIMEOUT_MS}"))
            rows = conn.execute(
                ADDRESSES_SQL,
                {
                    "patterns": patterns,
                    "query": query,
                    "candidates": ADDRESS_CANDIDATES,
                    "limit": limit,
                },
            ).all()
    except DBAPIError:
        return None
    return [
        GeocodeResult(
            kind="address",
            code=None,
            label=row.label,
            detail=row.detail,
            lat=row.lat,
            lon=row.lon,
            bbox=None,
            population=None,
        )
        for row in rows
    ]


def geocode(conn: Connection, query: str, limit: int) -> GeocodeResponse:
    """Rank exact name matches first, then addresses, then similar names by population."""
    area_rows = conn.execute(AREAS_SQL, {"query": query, "limit": limit}).all()
    areas = [
        (
            row.exact,
            GeocodeResult(
                kind=row.kind,
                code=row.code,
                label=row.label,
                detail=row.detail,
                lat=row.lat,
                lon=row.lon,
                bbox=_bbox(row.envelope),
                population=row.population,
            ),
        )
        for row in area_rows
    ]
    addresses = _search_addresses(conn, query, limit)
    results = [item for exact, item in areas if exact]
    results += addresses or []
    results += [item for exact, item in areas if not exact]
    return GeocodeResponse(results=results[:limit], addresses_searched=addresses is not None)
