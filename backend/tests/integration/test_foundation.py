from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import MultiPolygon, box
from sqlalchemy import Connection, text

from klimakompas.api.app import create_app, get_connection
from klimakompas.core.db import upsert_rows
from klimakompas.pipeline.grid import add_populated_cells_outside, build_grid
from klimakompas.pipeline.tiles import refresh_tiles
from klimakompas.sources.gml import to_ewkb

# Two municipalities side by side. The boundary at x = 4_800_600 splits one cell 60/40.
WEST = MultiPolygon([box(4_800_000, 2_500_000, 4_800_600, 2_502_000)])
EAST = MultiPolygon([box(4_800_600, 2_500_000, 4_802_000, 2_502_000)])
LOCATION = {
    "zupanija": "14",
    "west_jls": "03123",
    "east_jls": "06149",
    "west_naselje": "045691",
    "east_naselje": "063819",
}


def seed(conn: Connection) -> None:
    upsert_rows(
        conn,
        "ref.zupanije",
        ("code", "name", "geom"),
        ("code",),
        [(LOCATION["zupanija"], "Osječko-baranjska županija", to_ewkb(WEST.union(EAST)))],
    )
    upsert_rows(
        conn,
        "ref.jls",
        ("code", "name", "kind", "zupanija_code", "geom"),
        ("code",),
        [
            (LOCATION["west_jls"], "Osijek", "grad", LOCATION["zupanija"], to_ewkb(WEST)),
            (LOCATION["east_jls"], "Šodolovci", "opcina", LOCATION["zupanija"], to_ewkb(EAST)),
        ],
    )
    upsert_rows(
        conn,
        "ref.naselja",
        ("code", "name", "jls_code", "geom", "point"),
        ("code",),
        [
            (
                LOCATION["west_naselje"],
                "Osijek",
                LOCATION["west_jls"],
                to_ewkb(WEST),
                to_ewkb(WEST.representative_point()),
            ),
            (
                LOCATION["east_naselje"],
                "Čepin Šodolovački",
                LOCATION["east_jls"],
                to_ewkb(EAST),
                to_ewkb(EAST.representative_point()),
            ),
        ],
    )
    upsert_rows(
        conn,
        "pop.jls_2021",
        ("jls_code", "pop_total", "pop_ge65", "pop_lt15"),
        ("jls_code",),
        [(LOCATION["west_jls"], 96313, 20000, 12000), (LOCATION["east_jls"], 1500, 400, 200)],
    )
    upsert_rows(
        conn,
        "pop.naselja_2021",
        ("naselje_code", "pop_total", "pop_ge65", "pop_lt15"),
        ("naselje_code",),
        [(LOCATION["west_naselje"], 75535, 15000, 9000)],
    )
    conn.execute(
        text(
            "INSERT INTO ref.addresses (id, label, street, house_number, naselje_code, "
            "naselje_name, jls_code, search_text, geom) VALUES ('KB.1', "
            "'Trg slobode 7 Osijek 31000 Osijek', 'Trg slobode', '7', :naselje, 'Osijek', :jls, "
            "ref.normalize_search('Trg slobode 7 Osijek 31000 Osijek'), "
            "ST_SetSRID(ST_MakePoint(4800100, 2500100), 3035))"
        ),
        {"naselje": LOCATION["west_naselje"], "jls": LOCATION["west_jls"]},
    )


@pytest.fixture
def seeded(conn: Connection) -> Connection:
    seed(conn)
    return conn


def cell(conn: Connection, cell_id: str) -> dict[str, object]:
    row = conn.execute(
        text("SELECT * FROM ref.grid_1km WHERE cell_id = :id"), {"id": cell_id}
    ).one()
    return dict(row._mapping)


def test_grid_ids_follow_inspire_and_assign_by_largest_overlap(seeded: Connection) -> None:
    assert build_grid(seeded) == 4

    split = cell(seeded, "CRS3035RES1000mN2500000E4800000")
    assert split["jls_code"] == LOCATION["west_jls"]
    assert split["naselje_code"] == LOCATION["west_naselje"]
    assert split["zupanija_code"] == LOCATION["zupanija"]
    assert split["land_share"] == pytest.approx(1.0)
    assert split["overlap_share"] == pytest.approx(0.6)

    east = cell(seeded, "CRS3035RES1000mN2501000E4801000")
    assert east["jls_code"] == LOCATION["east_jls"]
    assert east["overlap_share"] == pytest.approx(1.0)


def test_cell_geometry_is_lower_left_anchored(seeded: Connection) -> None:
    build_grid(seeded)
    bounds = seeded.execute(
        text(
            "SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) "
            "FROM ref.grid_1km WHERE cell_id = 'CRS3035RES1000mN2500000E4800000'"
        )
    ).one()
    assert tuple(bounds) == (4_800_000, 2_500_000, 4_801_000, 2_501_000)


def test_populated_cell_outside_polygons_goes_to_the_nearest_unit(seeded: Connection) -> None:
    build_grid(seeded)
    assert add_populated_cells_outside(seeded, ["CRS3035RES1000mN2500000E4795000"]) == 1
    outside = cell(seeded, "CRS3035RES1000mN2500000E4795000")
    assert outside["jls_code"] == LOCATION["west_jls"]
    assert outside["land_share"] == 0
    assert outside["overlap_share"] == 0


def test_build_grid_is_idempotent(seeded: Connection) -> None:
    build_grid(seeded)
    seeded.execute(text("DROP TABLE _parts, _cells, _overlap"))
    assert build_grid(seeded) == 4


def test_tile_views_refresh_in_web_mercator(seeded: Connection) -> None:
    build_grid(seeded)
    seeded.execute(
        text(
            "INSERT INTO pop.grid_2021 (cell_id, cntr_id, pop_total) "
            "VALUES ('CRS3035RES1000mN2500000E4800000', 'HR', 12), "
            "('CRS3035RES1000mN2501000E4800000', 'HR', 0)"
        )
    )
    refresh_tiles(seeded)
    assert seeded.execute(text("SELECT count(*) FROM tiles.jls")).scalar_one() == 2
    assert seeded.execute(text("SELECT count(*) FROM tiles.grid_pop")).scalar_one() == 1
    assert seeded.execute(text("SELECT DISTINCT ST_SRID(geom) FROM tiles.jls")).scalar_one() == 3857


@pytest.fixture
def client(seeded: Connection) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: seeded
    with TestClient(app) as test_client:
        yield test_client


def test_geocode_finds_name_without_diacritics(client: TestClient) -> None:
    body = client.get("/api/v1/geocode", params={"q": "sodolovci"}).json()
    assert body["results"][0]["label"] == "Šodolovci"
    assert body["results"][0]["kind"] == "municipality"
    assert body["results"][0]["detail"] == "Općina, Osječko-baranjska županija"
    assert body["results"][0]["population"] == 1500


def test_geocode_returns_wgs84_coordinates_and_bbox(client: TestClient) -> None:
    result = client.get("/api/v1/geocode", params={"q": "Osijek"}).json()["results"][0]
    assert 15 < result["lon"] < 30
    assert 40 < result["lat"] < 55
    west, south, east, north = result["bbox"]
    assert west < east and south < north


def test_geocode_ranks_exact_name_before_addresses(client: TestClient) -> None:
    kinds = [item["kind"] for item in client.get("/api/v1/geocode?q=Osijek").json()["results"]]
    assert kinds[0] in {"settlement", "municipality"}
    assert "address" in kinds


def test_geocode_finds_address_with_house_number(client: TestClient) -> None:
    body = client.get("/api/v1/geocode", params={"q": "trg slobode 7"}).json()
    assert body["addresses_searched"] is True
    assert body["results"][0]["kind"] == "address"
    assert body["results"][0]["label"] == "Trg slobode 7 Osijek 31000 Osijek"
    assert body["results"][0]["detail"] == "Osijek"


def test_geocode_treats_like_wildcards_literally(client: TestClient) -> None:
    body = client.get("/api/v1/geocode", params={"q": "%%%"}).json()
    assert body["results"] == []


def test_geocode_with_no_match_is_empty_not_an_error(client: TestClient) -> None:
    response = client.get("/api/v1/geocode", params={"q": "xqzxqzxqz"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_validation_error_is_rfc9457_and_does_not_echo_the_query(client: TestClient) -> None:
    response = client.get("/api/v1/geocode", params={"q": "x"})
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert '"x"' not in response.text
    assert response.json()["status"] == 422


def test_sources_list_has_attribution_and_status(client: TestClient) -> None:
    sources = {item["id"]: item for item in client.get("/api/v1/sources").json()}
    assert sources["dgu_au"]["attribution"] == "Izvor: Geoportal Državne geodetske uprave"
    assert sources["dgu_au"]["verified_on"] == "2026-11-01"


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/ready").json()["database"] is True
