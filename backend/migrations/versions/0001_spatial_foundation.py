"""Spatial foundation: ref, pop, meta and tiles schemas (SPEC §13)."""

from alembic import op

revision = "0001"
down_revision = None

STATEMENTS = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE SCHEMA ref;
CREATE SCHEMA pop;
CREATE SCHEMA meta;
CREATE SCHEMA tiles;

-- unaccent() is only STABLE, so generated columns and indexes need this wrapper.
CREATE FUNCTION ref.normalize_search(value text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
RETURN public.unaccent('public.unaccent'::regdictionary, lower(value));

CREATE TABLE ref.zupanije (
    code text PRIMARY KEY,
    name text NOT NULL,
    geom geometry(MultiPolygon, 3035) NOT NULL
);
CREATE INDEX zupanije_geom_idx ON ref.zupanije USING gist (geom);

CREATE TABLE ref.jls (
    code text PRIMARY KEY,
    name text NOT NULL,
    kind text CHECK (kind IN ('grad', 'opcina')),
    zupanija_code text NOT NULL REFERENCES ref.zupanije (code),
    search_text text GENERATED ALWAYS AS (ref.normalize_search(name)) STORED,
    geom geometry(MultiPolygon, 3035) NOT NULL
);
CREATE INDEX jls_geom_idx ON ref.jls USING gist (geom);
CREATE INDEX jls_zupanija_idx ON ref.jls (zupanija_code);
CREATE INDEX jls_search_idx ON ref.jls USING gin (search_text gin_trgm_ops);

CREATE TABLE ref.naselja (
    code text PRIMARY KEY,
    name text NOT NULL,
    jls_code text NOT NULL REFERENCES ref.jls (code),
    search_text text GENERATED ALWAYS AS (ref.normalize_search(name)) STORED,
    geom geometry(MultiPolygon, 3035),
    point geometry(Point, 3035)
);
CREATE INDEX naselja_geom_idx ON ref.naselja USING gist (geom);
CREATE INDEX naselja_jls_idx ON ref.naselja (jls_code);
CREATE INDEX naselja_search_idx ON ref.naselja USING gin (search_text gin_trgm_ops);

CREATE TABLE ref.grid_1km (
    cell_id text PRIMARY KEY,
    geom geometry(Polygon, 3035) NOT NULL,
    centroid geometry(Point, 3035) NOT NULL,
    land_share double precision NOT NULL CHECK (land_share BETWEEN 0 AND 1),
    jls_code text NOT NULL REFERENCES ref.jls (code),
    naselje_code text NOT NULL REFERENCES ref.naselja (code),
    zupanija_code text NOT NULL REFERENCES ref.zupanije (code),
    overlap_share double precision NOT NULL CHECK (overlap_share BETWEEN 0 AND 1)
);
CREATE INDEX grid_1km_geom_idx ON ref.grid_1km USING gist (geom);
CREATE INDEX grid_1km_jls_idx ON ref.grid_1km (jls_code);
CREATE INDEX grid_1km_naselje_idx ON ref.grid_1km (naselje_code);

CREATE TABLE ref.addresses (
    id text PRIMARY KEY,
    label text NOT NULL,
    street text,
    house_number text,
    naselje_code text REFERENCES ref.naselja (code),
    naselje_name text,
    jls_code text REFERENCES ref.jls (code),
    search_text text NOT NULL,
    geom geometry(Point, 3035) NOT NULL
);
CREATE INDEX addresses_search_idx ON ref.addresses USING gin (search_text gin_trgm_ops);

CREATE TABLE pop.naselja_2021 (
    naselje_code text PRIMARY KEY REFERENCES ref.naselja (code),
    pop_total integer NOT NULL CHECK (pop_total >= 0),
    pop_ge65 integer NOT NULL CHECK (pop_ge65 >= 0),
    pop_lt15 integer NOT NULL CHECK (pop_lt15 >= 0)
);

CREATE TABLE pop.jls_2021 (
    jls_code text PRIMARY KEY REFERENCES ref.jls (code),
    pop_total integer NOT NULL CHECK (pop_total >= 0),
    pop_ge65 integer NOT NULL CHECK (pop_ge65 >= 0),
    pop_lt15 integer NOT NULL CHECK (pop_lt15 >= 0)
);

CREATE TABLE pop.grid_2021 (
    cell_id text PRIMARY KEY REFERENCES ref.grid_1km (cell_id),
    cntr_id text NOT NULL,
    pop_total integer,
    pop_ge65 integer,
    pop_lt15 integer,
    suppressed boolean NOT NULL DEFAULT false,
    share_ge65 double precision CHECK (share_ge65 BETWEEN 0 AND 1),
    share_lt15 double precision CHECK (share_lt15 BETWEEN 0 AND 1),
    age_share_source text CHECK (age_share_source IN ('cell', 'naselje', 'jls'))
);

CREATE TABLE meta.sources (
    source_id text PRIMARY KEY,
    last_success_at timestamptz,
    last_status text,
    last_error text,
    last_modified_source timestamptz,
    record_count bigint
);

CREATE TABLE meta.etl_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id text NOT NULL,
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    status text NOT NULL,
    rows bigint,
    error text,
    artifacts jsonb
);

CREATE TABLE meta.dq_checks (
    source_id text NOT NULL,
    check_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('pass', 'fail')),
    value double precision,
    details jsonb,
    checked_at timestamptz NOT NULL,
    PRIMARY KEY (source_id, check_id)
);

CREATE MATERIALIZED VIEW tiles.jls AS
SELECT j.code, j.name, j.kind, j.zupanija_code, p.pop_total,
       ST_Transform(ST_SimplifyPreserveTopology(j.geom, 25), 3857)::geometry(Geometry, 3857) AS geom
FROM ref.jls j
LEFT JOIN pop.jls_2021 p ON p.jls_code = j.code
WITH NO DATA;
CREATE UNIQUE INDEX jls_code_idx ON tiles.jls (code);
CREATE INDEX jls_geom_idx ON tiles.jls USING gist (geom);

CREATE MATERIALIZED VIEW tiles.grid_pop AS
SELECT c.cell_id, g.pop_total, c.jls_code,
       ST_Transform(c.geom, 3857)::geometry(Polygon, 3857) AS geom
FROM pop.grid_2021 g
JOIN ref.grid_1km c USING (cell_id)
WHERE g.pop_total > 0
WITH NO DATA;
CREATE UNIQUE INDEX grid_pop_cell_idx ON tiles.grid_pop (cell_id);
CREATE INDEX grid_pop_geom_idx ON tiles.grid_pop USING gist (geom);
"""


def upgrade() -> None:
    op.execute(STATEMENTS)
