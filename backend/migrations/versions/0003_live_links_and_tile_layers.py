"""Link warnings to counties, track AZO series and add the tile layers from SPEC §12."""

from alembic import op

revision = "0003"
down_revision = "0002"

STATEMENTS = """
ALTER TABLE live.warnings ADD COLUMN zupanija_code text REFERENCES ref.zupanije (code);
ALTER TABLE live.warnings ADD COLUMN awareness_type text;
CREATE INDEX warnings_zupanija_idx ON live.warnings (zupanija_code);

CREATE TABLE live.aq_series (
    station_id text NOT NULL REFERENCES live.aq_stations (station_id),
    pollutant_id text NOT NULL,
    last_checked_at timestamptz,
    last_obs_at timestamptz,
    PRIMARY KEY (station_id, pollutant_id)
);

ALTER TABLE live.fire_index ADD COLUMN naselje_code text REFERENCES ref.naselja (code);

DROP TABLE ref.dhmz_regions;
DROP MATERIALIZED VIEW tiles.cells;

CREATE MATERIALIZED VIEW tiles.grid_risk AS
SELECT c.cell_id,
       r.pop_total,
       f.h_flood, h.h_heat, x.h_fire, a.h_air, a.pm25_annual,
       r.ikr, r.ikr_class, r.class_flood, r.class_heat, r.class_fire, r.class_air,
       p.share_ge65,
       ST_Transform(c.geom, 3857)::geometry(Polygon, 3857) AS geom
FROM ref.grid_1km c
LEFT JOIN haz.flood_cell f USING (cell_id)
LEFT JOIN haz.heat_cell h USING (cell_id)
LEFT JOIN haz.fire_cell x USING (cell_id)
LEFT JOIN haz.air_cell a USING (cell_id)
LEFT JOIN pop.grid_2021 p USING (cell_id)
LEFT JOIN idx.current_risk_cell r USING (cell_id)
WITH NO DATA;
CREATE UNIQUE INDEX grid_risk_cell_idx ON tiles.grid_risk (cell_id);
CREATE INDEX grid_risk_geom_idx ON tiles.grid_risk USING gist (geom);

CREATE MATERIALIZED VIEW tiles.zupanije AS
SELECT z.code, z.name,
       ST_Transform(ST_SimplifyPreserveTopology(z.geom, 50), 3857)::geometry(Geometry, 3857) AS geom
FROM ref.zupanije z
WITH NO DATA;
CREATE UNIQUE INDEX zupanije_code_idx ON tiles.zupanije (code);
CREATE INDEX zupanije_tile_geom_idx ON tiles.zupanije USING gist (geom);

CREATE MATERIALIZED VIEW tiles.naselja AS
SELECT n.code, n.name, n.jls_code, r.ikr_popw, r.ikr_class, p.pop_total,
       ST_Transform(ST_SimplifyPreserveTopology(n.geom, 10), 3857)::geometry(Geometry, 3857) AS geom
FROM ref.naselja n
LEFT JOIN idx.current_risk_naselja r ON r.naselje_code = n.code
LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code
WITH NO DATA;
CREATE UNIQUE INDEX naselja_code_idx ON tiles.naselja (code);
CREATE INDEX naselja_tile_geom_idx ON tiles.naselja USING gist (geom);

CREATE MATERIALIZED VIEW tiles.nature AS
SELECT a.id, a.layer, a.name, a.category,
       ST_Transform(ST_SimplifyPreserveTopology(a.geom, 10), 3857)::geometry(Geometry, 3857) AS geom
FROM live.nature_areas a
WITH NO DATA;
CREATE UNIQUE INDEX nature_id_idx ON tiles.nature (id);
CREATE INDEX nature_tile_geom_idx ON tiles.nature USING gist (geom);
"""


def upgrade() -> None:
    op.execute(STATEMENTS)
