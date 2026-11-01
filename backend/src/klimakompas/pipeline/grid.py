"""INSPIRE 1 km grid over the settlement polygons (SPEC §5.2)."""

from sqlalchemy import Connection, text

CELL_AREA_M2 = 1_000_000

BUILD_GRID_SQL = """
CREATE TEMP TABLE _parts ON COMMIT DROP AS
SELECT n.code AS naselje_code, n.jls_code, ST_Subdivide(n.geom, 128) AS geom
FROM ref.naselja n;
CREATE INDEX ON _parts USING gist (geom);
ANALYZE _parts;

-- ST_SquareGrid cells are anchored at the origin, so i and j give the INSPIRE lower-left corner.
CREATE TEMP TABLE _cells ON COMMIT DROP AS
SELECT 'CRS3035RES1000mN' || (g.j * 1000) || 'E' || (g.i * 1000) AS cell_id, g.geom
FROM (SELECT ST_SetSRID(ST_Extent(geom), 3035) AS extent FROM _parts) e
CROSS JOIN LATERAL ST_SquareGrid(1000, e.extent) g;
CREATE INDEX ON _cells USING gist (geom);
ANALYZE _cells;

CREATE TEMP TABLE _overlap ON COMMIT DROP AS
SELECT c.cell_id, p.naselje_code, p.jls_code,
       SUM(ST_Area(ST_Intersection(c.geom, p.geom))) AS area
FROM _cells c
JOIN _parts p ON ST_Intersects(c.geom, p.geom)
GROUP BY 1, 2, 3
HAVING SUM(ST_Area(ST_Intersection(c.geom, p.geom))) > 0;
CREATE INDEX ON _overlap (cell_id);

INSERT INTO ref.grid_1km (cell_id, geom, centroid, land_share, jls_code, naselje_code,
                          zupanija_code, overlap_share)
WITH totals AS (
    SELECT cell_id, SUM(area) AS area FROM _overlap GROUP BY cell_id
), best_jls AS (
    SELECT DISTINCT ON (cell_id) cell_id, jls_code, area
    FROM (SELECT cell_id, jls_code, SUM(area) AS area FROM _overlap GROUP BY 1, 2) by_jls
    ORDER BY cell_id, area DESC, jls_code
), best_naselje AS (
    SELECT DISTINCT ON (o.cell_id) o.cell_id, o.naselje_code
    FROM _overlap o
    JOIN best_jls b ON b.cell_id = o.cell_id AND b.jls_code = o.jls_code
    ORDER BY o.cell_id, o.area DESC, o.naselje_code
)
SELECT c.cell_id, c.geom, ST_Centroid(c.geom),
       LEAST(t.area / :cell_area, 1), b.jls_code, n.naselje_code, j.zupanija_code,
       LEAST(b.area / t.area, 1)
FROM _cells c
JOIN totals t USING (cell_id)
JOIN best_jls b USING (cell_id)
JOIN best_naselje n USING (cell_id)
JOIN ref.jls j ON j.code = b.jls_code
ON CONFLICT (cell_id) DO UPDATE SET
    land_share = EXCLUDED.land_share, jls_code = EXCLUDED.jls_code,
    naselje_code = EXCLUDED.naselje_code, zupanija_code = EXCLUDED.zupanija_code,
    overlap_share = EXCLUDED.overlap_share;
"""

# Census cells reported by Croatia can lie just outside the settlement polygons. They keep the
# nearest unit, with land_share and overlap_share at 0 to mark that the assignment is approximate.
ADD_POPULATED_OUTSIDE_SQL = """
INSERT INTO ref.grid_1km (cell_id, geom, centroid, land_share, jls_code, naselje_code,
                          zupanija_code, overlap_share)
SELECT o.cell_id, o.geom, ST_Centroid(o.geom), 0, n.jls_code, n.code, j.zupanija_code, 0
FROM (
    SELECT cell_id, ST_MakeEnvelope(x, y, x + 1000, y + 1000, 3035) AS geom
    FROM _outside
) o
CROSS JOIN LATERAL (
    SELECT code, jls_code FROM ref.naselja ORDER BY geom <-> o.geom LIMIT 1
) n
JOIN ref.jls j ON j.code = n.jls_code
ON CONFLICT (cell_id) DO NOTHING
"""


def cell_id(x_ll: int, y_ll: int) -> str:
    return f"CRS3035RES1000mN{y_ll}E{x_ll}"


def parse_cell_id(value: str) -> tuple[int, int]:
    """Return (x_ll, y_ll) from a GRD_ID."""
    north, east = value.removeprefix("CRS3035RES1000mN").split("E")
    return int(east), int(north)


def build_grid(conn: Connection) -> int:
    """Generate cells that intersect settlements and assign each by the largest overlap."""
    for statement in BUILD_GRID_SQL.split(";\n"):
        if statement.strip():
            conn.execute(text(statement), {"cell_area": CELL_AREA_M2})
    count: int = conn.execute(text("SELECT count(*) FROM ref.grid_1km")).scalar_one()
    return count


def add_populated_cells_outside(conn: Connection, cell_ids: list[str]) -> int:
    """Add populated census cells missing from the grid and return how many were added."""
    conn.execute(text("DROP TABLE IF EXISTS _outside"))
    conn.execute(text("CREATE TEMP TABLE _outside (cell_id text, x int, y int) ON COMMIT DROP"))
    for value in cell_ids:
        x_ll, y_ll = parse_cell_id(value)
        conn.execute(
            text("INSERT INTO _outside VALUES (:cell_id, :x, :y)"),
            {"cell_id": value, "x": x_ll, "y": y_ll},
        )
    return conn.execute(text(ADD_POPULATED_OUTSIDE_SQL)).rowcount
