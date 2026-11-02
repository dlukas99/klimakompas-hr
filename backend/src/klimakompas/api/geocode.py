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

# An area is shown at the centre of its most populated 1 km cell: the geometric centre of a
# settlement often lies in fields or forest, and its card would then show no residents.
AREAS_SQL = text("""
WITH q AS (SELECT ref.normalize_search(:query) AS value),
areas AS (
    SELECT 'settlement' AS kind, n.code, n.name AS label, j.name AS detail, n.search_text,
           coalesce((
               SELECT c.centroid FROM ref.grid_1km c JOIN pop.grid_2021 g USING (cell_id)
               WHERE c.naselje_code = n.code AND g.pop_total > 0
               ORDER BY g.pop_total DESC LIMIT 1
           ), n.point) AS location,
           n.geom, p.pop_total AS population, n.jls_code
    FROM ref.naselja n
    JOIN ref.jls j ON j.code = n.jls_code
    LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code, q
    WHERE (n.search_text % q.value OR starts_with(n.search_text, q.value))
      AND (CAST(:jls AS text) IS NULL OR n.jls_code = :jls)
      AND 'settlement' = ANY (CAST(:kinds AS text[]))
    UNION ALL
    SELECT 'municipality', j.code, j.name,
           (CASE j.kind WHEN 'grad' THEN 'Grad' WHEN 'opcina' THEN 'Općina' END) || ', ' || z.name,
           j.search_text,
           -- The largest settlement stands for the municipality, so the card names the seat
           -- and not some other village whose single cell happens to be denser.
           coalesce((
               SELECT c.centroid FROM ref.grid_1km c JOIN pop.grid_2021 g USING (cell_id)
               WHERE g.pop_total > 0 AND c.naselje_code = (
                   SELECT n2.code FROM ref.naselja n2
                   JOIN pop.naselja_2021 p2 ON p2.naselje_code = n2.code
                   WHERE n2.jls_code = j.code ORDER BY p2.pop_total DESC LIMIT 1
               )
               ORDER BY g.pop_total DESC LIMIT 1
           ), ST_PointOnSurface(j.geom)),
           j.geom, p.pop_total, j.code
    FROM ref.jls j
    JOIN ref.zupanije z ON z.code = j.zupanija_code
    LEFT JOIN pop.jls_2021 p ON p.jls_code = j.code, q
    WHERE (j.search_text % q.value OR starts_with(j.search_text, q.value))
      AND (CAST(:jls AS text) IS NULL OR j.code = :jls)
      AND 'municipality' = ANY (CAST(:kinds AS text[]))
), ranked AS (
    SELECT a.*, a.search_text = q.value AS exact, similarity(a.search_text, q.value) AS score
    FROM areas a, q
    ORDER BY exact DESC, score DESC, population DESC NULLS LAST, kind
    LIMIT :limit
)
SELECT kind, code, label, detail, population, score, exact, jls_code,
       ST_Y(ST_Transform(location, 4326)) AS lat, ST_X(ST_Transform(location, 4326)) AS lon,
       ST_AsGeoJSON(ST_Envelope(ST_Transform(geom, 4326))) AS envelope
FROM ranked
""")

ADDRESSES_SQL = text("""
WITH candidates AS (
    SELECT a.label, a.house_number, a.jls_code, a.geom, a.search_text
    FROM ref.addresses a
    WHERE a.search_text LIKE ALL (:patterns)
      AND (CAST(:jls AS text) IS NULL OR a.jls_code = :jls)
      AND (cardinality(CAST(:numbers AS text[])) = 0
           OR a.search_text ~ ALL (CAST(:number_patterns AS text[])))
    LIMIT :candidates
)
SELECT c.label, j.name AS detail, c.jls_code, ST_Y(ST_Transform(c.geom, 4326)) AS lat,
       ST_X(ST_Transform(c.geom, 4326)) AS lon,
       lower(c.house_number) = ANY (CAST(:numbers AS text[])) AS exact_number,
       similarity(c.search_text, ref.normalize_search(:query)) AS score
FROM candidates c
LEFT JOIN ref.jls j ON j.code = c.jls_code
ORDER BY exact_number DESC, score DESC, length(c.label), c.label
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


def _search_addresses(
    conn: Connection, query: str, limit: int, jls: str | None
) -> list[GeocodeResult] | None:
    """Return matches, or None if the search timed out. Only names remain in that case."""
    tokens = _tokens(query)
    # A trigram index needs at least one token of three characters to narrow the search.
    if not any(len(token) >= MIN_TOKEN_LENGTH_FOR_INDEX for token in tokens):
        return None
    normalized: str = conn.execute(
        text("SELECT ref.normalize_search(:value)"), {"value": " ".join(tokens)}
    ).scalar_one()
    words = normalized.split(" ")
    # House numbers match whole words, so "1" does not find 143 or 21.
    numbers = [word for word in words if word[0].isdigit()]
    patterns = [f"%{_escape_like(word)}%" for word in words if word not in numbers] or ["%"]
    number_patterns = [rf"\m{re.escape(number)}\M" for number in numbers]
    try:
        with conn.begin_nested():
            conn.execute(text(f"SET LOCAL statement_timeout = {ADDRESS_TIMEOUT_MS}"))
            rows = conn.execute(
                ADDRESSES_SQL,
                {
                    "patterns": patterns,
                    "numbers": numbers,
                    "number_patterns": number_patterns,
                    "query": query,
                    "candidates": ADDRESS_CANDIDATES,
                    "limit": limit,
                    "jls": jls,
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
            jls_code=row.jls_code,
        )
        for row in rows
    ]


ALL_KINDS = ("address", "settlement", "municipality")


def geocode(
    conn: Connection,
    query: str,
    limit: int,
    kinds: tuple[str, ...] = ALL_KINDS,
    jls: str | None = None,
) -> GeocodeResponse:
    """Rank exact name matches first, then addresses, then similar names by population.

    `jls` limits every result to one municipality or town, and `kinds` to some result types.
    """
    area_rows = conn.execute(
        AREAS_SQL, {"query": query, "limit": limit, "kinds": list(kinds), "jls": jls}
    ).all()
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
                jls_code=row.jls_code,
            ),
        )
        for row in area_rows
    ]
    addresses = _search_addresses(conn, query, limit, jls) if "address" in kinds else []
    results = [item for exact, item in areas if exact]
    results += addresses or []
    results += [item for exact, item in areas if not exact]
    return GeocodeResponse(results=results[:limit], addresses_searched=addresses is not None)
