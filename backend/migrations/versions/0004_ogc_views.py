"""Views in EPSG:4326 for the OGC API collections (SPEC §12)."""

from alembic import op

revision = "0004"
down_revision = "0003"

STATEMENTS = """
CREATE SCHEMA ogc;

CREATE VIEW ogc.grid_risk AS
SELECT r.cell_id, CASE WHEN r.pop_total < 10 THEN NULL ELSE r.pop_total END AS pop_total,
       r.ikr, r.ikr_class, r.class_flood, r.class_heat, r.class_fire, r.class_air,
       ST_Transform(c.geom, 4326)::geometry(Polygon, 4326) AS geom
FROM idx.current_risk_cell r JOIN ref.grid_1km c USING (cell_id);

CREATE VIEW ogc.jls_risk AS
SELECT j.code, j.name, j.kind, r.pop, r.ikr_popw, r.ikr_class, r.rank_hr, r.rank_zup,
       ST_Transform(j.geom, 4326)::geometry(MultiPolygon, 4326) AS geom
FROM ref.jls j JOIN idx.current_risk_jls r ON r.jls_code = j.code;

CREATE VIEW ogc.aq_stations AS
SELECT s.station_id, s.name, s.network, s.last_obs_at,
       ST_Transform(s.geom, 4326)::geometry(Point, 4326) AS geom
FROM live.aq_stations s WHERE s.geom IS NOT NULL;

CREATE VIEW ogc.warnings_active AS
SELECT w.id, w.event, w.level, w.level_name, w.onset, w.expires, w.area_desc,
       ST_Transform(z.geom, 4326)::geometry(MultiPolygon, 4326) AS geom
FROM live.warnings w JOIN ref.zupanije z ON z.code = w.zupanija_code
WHERE w.expires IS NULL OR w.expires > now();
"""


def upgrade() -> None:
    op.execute(STATEMENTS)
