import json
from datetime import timedelta
from pathlib import Path

import pytest
from lxml import etree

from klimakompas.live.parsers import (
    county_key,
    eaqi_class,
    parse_aq,
    parse_cap,
    parse_fire_index,
    parse_heatwave,
    parse_k1_hot_days,
    parse_stations,
)
from klimakompas.sources.dgu_ad import parse_addresses, parse_settlement_names, parse_street_names
from klimakompas.sources.dgu_au import parse_units
from klimakompas.sources.dzs_naselja import parse_table
from klimakompas.sources.estat_census import CensusCell, parse_cells
from klimakompas.sources.gml import EPSG_3035, GML, parse_multisurface, parse_point

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_parses_real_administrative_units() -> None:
    with (FIXTURES / "dgu_au" / "administrative_units_sample.gml").open("rb") as stream:
        units = {unit.name: unit for unit in parse_units(stream)}

    assert {"Požega", "Požeško-slavonska županija", "Alaginci"} <= set(units)
    assert not any(name.startswith("SK ") for name in units)

    town = units["Požega"]
    assert (town.code, town.level) == ("03514", "jls")
    settlement = units["Alaginci"]
    assert (settlement.code, settlement.level) == ("000043", "naselje")
    assert settlement.upper_id == town.gml_id
    assert units["Požeško-slavonska županija"].level == "zupanija"

    assert settlement.geom.is_valid
    assert settlement.geom.geom_type == "MultiPolygon"
    # Požega lies near 4.87M east, 2.51M north in EPSG:3035.
    x, y = settlement.geom.centroid.coords[0]
    assert 4_700_000 < x < 5_100_000
    assert 2_300_000 < y < 2_700_000


def test_parses_real_addresses_with_their_links() -> None:
    folder = FIXTURES / "dgu_ad"
    with (folder / "thoroughfare_sample.gml").open("rb") as stream:
        streets = parse_street_names(stream)
    with (folder / "admin_unit_name_sample.gml").open("rb") as stream:
        settlements = parse_settlement_names(stream)
    with (folder / "address_sample.gml").open("rb") as stream:
        addresses = list(parse_addresses(stream, streets, settlements))

    first = addresses[0]
    assert first.id == "KB.0000000135"
    assert first.label == "Brežna ulica 33 Andraševec 49243 Oroslavje"
    assert first.street == "Brežna ulica"
    assert first.house_number == "33"
    assert first.naselje_name == "Andraševec"
    assert first.naselje_code is not None and len(first.naselje_code) == 6


def test_settlement_names_skip_the_country_entry() -> None:
    with (FIXTURES / "dgu_ad" / "admin_unit_name_sample.gml").open("rb") as stream:
        names = parse_settlement_names(stream)
    assert names
    assert "Republika Hrvatska" not in {name for _, name in names.values()}


def _point(srs: str, position: str) -> object:
    return etree.fromstring(
        f'<gml:Point xmlns:gml="{GML[1:-1]}" srsName="{srs}">'
        f"<gml:pos>{position}</gml:pos></gml:Point>"
    )


def test_point_swaps_northing_easting_into_x_y() -> None:
    point = parse_point(_point(EPSG_3035, "2561799.19 4781765.61"))
    assert (point.x, point.y) == (4781765.61, 2561799.19)


def test_rejects_unexpected_axis_order() -> None:
    with pytest.raises(ValueError, match="axis order"):
        parse_point(_point(EPSG_3035, "4781765.61 2561799.19"))


def test_rejects_other_crs() -> None:
    with pytest.raises(ValueError, match="EPSG:3035"):
        parse_point(_point("http://www.opengis.net/def/crs/EPSG/0/3765", "1 2"))


def test_repairs_self_intersecting_ring() -> None:
    gml = GML[1:-1]
    # A bow tie in northing, easting order: invalid as drawn, two valid triangles once repaired.
    ring = "2500000 5000000 2501000 5001000 2501000 5000000 2500000 5001000 2500000 5000000"
    element = etree.fromstring(
        f'<gml:MultiSurface xmlns:gml="{gml}" srsName="{EPSG_3035}"><gml:surfaceMember>'
        f"<gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>{ring}</gml:posList>"
        "</gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface>"
    )
    geometry = parse_multisurface(element)
    assert geometry.is_valid
    assert geometry.geom_type == "MultiPolygon"
    assert geometry.area > 0


def test_parses_real_census_rows_and_keeps_only_croatia() -> None:
    with (FIXTURES / "estat_census_grid_2021" / "census_sample.csv").open("rb") as stream:
        cells = list(parse_cells(stream))
    assert {cell.cntr_id for cell in cells} == {"HR", "HR-SI"}
    assert all(cell.cell_id.startswith("CRS3035RES1000mN") for cell in cells)
    assert all(cell.total is not None and cell.total >= 0 for cell in cells)


def test_census_confidential_codes_become_null(tmp_path: Path) -> None:
    path = tmp_path / "census.csv"
    path.write_text(
        "GRD_ID,T,Y_GE65,Y_LT15,CNTR_ID\nCRS3035RES1000mN1E2,10,-8888,-9999,HR\n", encoding="utf-8"
    )
    with path.open("rb") as stream:
        cell: CensusCell = next(parse_cells(stream))
    assert (cell.total, cell.ge65, cell.lt15) == (10, None, None)
    assert cell.suppressed


def test_parses_real_dzs_table() -> None:
    table = parse_table(FIXTURES / "dzs_naselja_2021" / "naselja_sample.xlsx")
    assert table.national.total == 3871833
    assert table.national.ge65 == 869239
    assert table.national.lt15 == 552416

    names = {(row.zupanija, row.jls, row.naselje) for row in table.settlements}
    assert ("Požeško-slavonska", "Požega", "Alaginci") in names
    # Zagreb rows have no JLS name, because the city is also a county.
    assert ("Grad Zagreb", "Grad Zagreb", "Žerjavinec") in names

    assert table.jls[("Požeško-slavonska", "Požega")][1] == "grad"
    zagreb_counts, zagreb_kind = table.jls[("Grad Zagreb", "Grad Zagreb")]
    assert zagreb_kind == "grad"
    assert zagreb_counts.total == 767131


def test_parses_hot_days_from_real_dhmz_table() -> None:
    body = (FIXTURES / "dhmz_climate" / "k1_osijek.xml").read_bytes()
    assert 10 < parse_k1_hot_days(body) < 60


def test_parses_real_cap_keeps_croatian_blocks_only() -> None:
    warnings = parse_cap((FIXTURES / "dhmz_cap" / "cap_hr_today.xml").read_bytes())
    assert warnings
    first = warnings[0]
    assert first.level in {2, 3, 4}
    assert first.level_name in {"yellow", "orange", "red"}
    assert first.onset is not None and first.onset.tzinfo is not None
    assert first.region_id is not None and first.region_id.startswith("HR")
    assert not any("coast" in warning.area_desc for warning in warnings)


def test_cap_without_alert_info_is_empty() -> None:
    body = b'<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>x</identifier></alert>'
    assert parse_cap(body) == []


def test_county_key_matches_register_and_cap_names() -> None:
    assert county_key("Zagrebačka županija") == county_key("Zagrebačka")
    assert county_key("Grad Zagreb") == "grad zagreb"


def test_parses_real_fire_index() -> None:
    day, stations = parse_fire_index((FIXTURES / "dhmz_fire_index" / "indeks.xml").read_bytes())
    assert day is not None
    assert stations[0].code == "14308"
    assert stations[0].fwi is not None


def test_off_season_heatwave_is_not_active() -> None:
    body = (FIXTURES / "dhmz_heatwave" / "toplinskival_off_season.xml").read_bytes()
    assert parse_heatwave(body) == {"active": False, "text": ""}


def test_parses_real_azo_values_as_utc_and_drops_impossible_ones() -> None:
    records = json.loads((FIXTURES / "azo_aq_rest" / "zagreb1_pm10_hourly.json").read_bytes())
    observations = parse_aq(records)
    assert observations
    assert observations[0].ts.utcoffset() == timedelta(0)
    assert parse_aq([{"vrijednost": -5, "vrijeme": 1, "mjernaJedinica": "x"}]) == []
    assert parse_aq([{"vrijednost": None, "vrijeme": 1}]) == []


def test_station_list_joins_ids_with_coordinates_by_name() -> None:
    form = {"options": [[[160, "Osijek-1"], [999, "Nepoznata"]]]}
    coordinates = {
        "data": [["Mreža", "OSIJEK-1", "", "", "", "", "", "", "", "", "", "45,56", "18,68"]]
    }
    stations = parse_stations(form, coordinates)
    assert (stations[0].id, stations[0].lat, stations[0].lon) == ("160", 45.56, 18.68)
    assert stations[1].lat is None


@pytest.mark.parametrize(
    ("value", "klass"), [(5.4, 1), (6, 2), (15, 2), (50, 3), (140, 5), (141, 6)]
)
def test_eaqi_classes_follow_the_eea_table(value: float, klass: int) -> None:
    assert eaqi_class(value, [5, 15, 50, 90, 140]) == klass
