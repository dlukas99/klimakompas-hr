"""Hazard, index, live and ML schemas (SPEC §13)."""

from alembic import op

revision = "0002"
down_revision = "0001"

STATEMENTS = """
CREATE SCHEMA haz;
CREATE SCHEMA idx;
CREATE SCHEMA live;
CREATE SCHEMA ml;

CREATE TABLE haz.flood_cell (
    cell_id text PRIMARY KEY REFERENCES ref.grid_1km (cell_id),
    s_rp10 double precision NOT NULL CHECK (s_rp10 BETWEEN 0 AND 1),
    s_rp100 double precision NOT NULL CHECK (s_rp100 BETWEEN 0 AND 1),
    s_rp500 double precision NOT NULL CHECK (s_rp500 BETWEEN 0 AND 1),
    s_deep_rp100 double precision NOT NULL CHECK (s_deep_rp100 BETWEEN 0 AND 1),
    eaf double precision NOT NULL CHECK (eaf >= 0),
    h_flood double precision NOT NULL CHECK (h_flood BETWEEN 0 AND 1),
    source_version text NOT NULL
);

CREATE TABLE haz.air_cell (
    cell_id text PRIMARY KEY REFERENCES ref.grid_1km (cell_id),
    pm25_annual double precision CHECK (pm25_annual BETWEEN 0 AND 1000),
    year integer NOT NULL,
    h_air double precision CHECK (h_air BETWEEN 0 AND 1),
    gap_filled boolean NOT NULL DEFAULT false
);

CREATE TABLE haz.landcover_cell (
    cell_id text PRIMARY KEY REFERENCES ref.grid_1km (cell_id),
    tree_share double precision NOT NULL CHECK (tree_share BETWEEN 0 AND 1),
    builtup_share double precision NOT NULL CHECK (builtup_share BETWEEN 0 AND 1),
    water_share double precision NOT NULL CHECK (water_share BETWEEN 0 AND 1),
    fuel_share double precision NOT NULL CHECK (fuel_share BETWEEN 0 AND 1)
);

CREATE TABLE haz.heat_cell (
    cell_id text PRIMARY KEY REFERENCES ref.grid_1km (cell_id),
    hot_days double precision,
    tropical_nights double precision,
    lst_median_c double precision,
    lst_delta_c double precision,
    tree_share double precision,
    builtup_share double precision,
    h_heat double precision CHECK (h_heat BETWEEN 0 AND 1)
);

CREATE TABLE haz.fire_cell (
    cell_id text PRIMARY KEY REFERENCES ref.grid_1km (cell_id),
    fwi_days double precision,
    fuel_share double precision,
    burnt_years_2km integer,
    h_fire double precision CHECK (h_fire BETWEEN 0 AND 1)
);

CREATE TABLE idx.runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    index_version text NOT NULL,
    config_sha text NOT NULL,
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    status text NOT NULL,
    source_versions jsonb
);

CREATE TABLE idx.risk_cell (
    run_id bigint NOT NULL REFERENCES idx.runs (run_id) ON DELETE CASCADE,
    cell_id text NOT NULL REFERENCES ref.grid_1km (cell_id),
    pop_total integer NOT NULL,
    h_flood double precision,
    h_heat double precision,
    h_fire double precision,
    h_air double precision,
    v_gen double precision,
    v_heat double precision,
    v_imputed boolean NOT NULL,
    r_flood double precision,
    r_heat double precision,
    r_fire double precision,
    r_air double precision,
    ikr double precision,
    ikr_class smallint,
    class_flood smallint,
    class_heat smallint,
    class_fire smallint,
    class_air smallint,
    PRIMARY KEY (run_id, cell_id)
);
CREATE INDEX risk_cell_cell_idx ON idx.risk_cell (cell_id);

CREATE TABLE idx.risk_jls (
    run_id bigint NOT NULL REFERENCES idx.runs (run_id) ON DELETE CASCADE,
    jls_code text NOT NULL REFERENCES ref.jls (code),
    pop integer NOT NULL,
    pop65 integer NOT NULL,
    ikr_popw double precision,
    ikr_class smallint,
    exposed jsonb NOT NULL,
    rank_hr integer,
    rank_zup integer,
    PRIMARY KEY (run_id, jls_code)
);

CREATE TABLE idx.risk_naselja (
    run_id bigint NOT NULL REFERENCES idx.runs (run_id) ON DELETE CASCADE,
    naselje_code text NOT NULL REFERENCES ref.naselja (code),
    pop integer NOT NULL,
    ikr_popw double precision,
    ikr_class smallint,
    exposed jsonb NOT NULL,
    PRIMARY KEY (run_id, naselje_code)
);

CREATE VIEW idx.current_run AS
SELECT max(run_id) AS run_id FROM idx.runs WHERE status = 'success';
CREATE VIEW idx.current_risk_cell AS
SELECT r.* FROM idx.risk_cell r JOIN idx.current_run c USING (run_id);
CREATE VIEW idx.current_risk_jls AS
SELECT r.* FROM idx.risk_jls r JOIN idx.current_run c USING (run_id);
CREATE VIEW idx.current_risk_naselja AS
SELECT r.* FROM idx.risk_naselja r JOIN idx.current_run c USING (run_id);

CREATE TABLE ref.dhmz_regions (
    region_id text PRIMARY KEY,
    name text NOT NULL,
    geom geometry(MultiPolygon, 3035)
);
CREATE INDEX dhmz_regions_geom_idx ON ref.dhmz_regions USING gist (geom);

CREATE TABLE live.aq_stations (
    station_id text PRIMARY KEY,
    name text NOT NULL,
    network text,
    geom geometry(Point, 3035),
    active boolean NOT NULL DEFAULT true,
    last_obs_at timestamptz
);
CREATE INDEX aq_stations_geom_idx ON live.aq_stations USING gist (geom);

CREATE TABLE live.aq_obs (
    station_id text NOT NULL REFERENCES live.aq_stations (station_id),
    pollutant_id text NOT NULL,
    ts timestamptz NOT NULL,
    value double precision NOT NULL,
    unit text,
    PRIMARY KEY (station_id, pollutant_id, ts)
);
CREATE INDEX aq_obs_ts_idx ON live.aq_obs (ts);

CREATE TABLE live.warnings (
    id text PRIMARY KEY,
    source_id text NOT NULL,
    event text,
    level smallint,
    level_name text,
    severity text,
    onset timestamptz,
    expires timestamptz,
    region_id text,
    nuts3 text,
    area_desc text,
    headline text,
    description text,
    instruction text,
    geom geometry(MultiPolygon, 3035),
    raw jsonb,
    fetched_at timestamptz NOT NULL
);
CREATE INDEX warnings_expires_idx ON live.warnings (expires);
CREATE INDEX warnings_geom_idx ON live.warnings USING gist (geom);

CREATE TABLE live.fire_index (
    station_code text PRIMARY KEY,
    station_name text,
    fwi double precision,
    category text,
    index_date date,
    in_season boolean NOT NULL,
    geom geometry(Point, 3035),
    fetched_at timestamptz NOT NULL
);

CREATE TABLE live.heatwave (
    id text PRIMARY KEY,
    region text,
    level text,
    day date,
    raw jsonb,
    fetched_at timestamptz NOT NULL
);

CREATE TABLE live.nature_areas (
    id text PRIMARY KEY,
    layer text NOT NULL,
    name text,
    category text,
    geom geometry(Geometry, 3035),
    fetched_at timestamptz NOT NULL
);
CREATE INDEX nature_areas_geom_idx ON live.nature_areas USING gist (geom);

CREATE TABLE meta.ckan_metadata (
    source_id text PRIMARY KEY,
    package_id text,
    title text,
    organization text,
    license_title text,
    metadata_modified timestamptz,
    fetched_at timestamptz NOT NULL
);

CREATE TABLE ml.models (
    model_version text PRIMARY KEY,
    trained_at timestamptz NOT NULL,
    params jsonb,
    metrics jsonb,
    artifact_path text
);

CREATE TABLE ml.pm25_forecast (
    station_id text NOT NULL,
    issued_at timestamptz NOT NULL,
    target_ts timestamptz NOT NULL,
    yhat double precision NOT NULL,
    lo double precision,
    hi double precision,
    model_version text NOT NULL,
    PRIMARY KEY (station_id, issued_at, target_ts)
);

CREATE MATERIALIZED VIEW tiles.cells AS
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
CREATE UNIQUE INDEX cells_cell_idx ON tiles.cells (cell_id);
CREATE INDEX cells_geom_idx ON tiles.cells USING gist (geom);

CREATE MATERIALIZED VIEW tiles.jls_risk AS
SELECT j.code, j.name, j.kind, r.ikr_popw, r.ikr_class, r.rank_hr, r.pop,
       ST_Transform(ST_SimplifyPreserveTopology(j.geom, 25), 3857)::geometry(Geometry, 3857) AS geom
FROM ref.jls j
LEFT JOIN idx.current_risk_jls r ON r.jls_code = j.code
WITH NO DATA;
CREATE UNIQUE INDEX jls_risk_code_idx ON tiles.jls_risk (code);
CREATE INDEX jls_risk_geom_idx ON tiles.jls_risk USING gist (geom);
"""


def upgrade() -> None:
    op.execute(STATEMENTS)
