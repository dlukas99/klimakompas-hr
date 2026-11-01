from klimakompas.core.config import load_index_config, load_sources, load_thresholds

CATALOG_IDS = {
    "dgu_au",
    "dgu_ad",
    "dzs_naselja_2021",
    "estat_census_grid_2021",
    "jrc_efas_flood",
    "hv_flood_wms",
    "eea_pm25_1km",
    "azo_aq_rest",
    "dhmz_cap",
    "dhmz_heatwave",
    "dhmz_fire_index",
    "dhmz_weather",
    "dhmz_climate",
    "bioportal_wfs",
    "ecde",
    "landsat_lst",
    "esa_worldcover",
    "burnt_areas",
    "open_meteo",
    "ckan",
    "dgu_dof",
    "basemap",
    "jrc_flood_events",
}


def test_registry_covers_the_catalog_once() -> None:
    ids = [source.id for source in load_sources()]
    assert len(ids) == len(set(ids))
    assert set(ids) == CATALOG_IDS


def test_sources_without_automated_access_have_no_probes() -> None:
    sources = {source.id: source for source in load_sources()}
    assert sources["hv_flood_wms"].verify.policy == "robots_only"
    assert sources["hv_flood_wms"].verify.probes == []
    assert sources["hv_flood_wms"].robots_allowed is False


def test_open_meteo_runs_under_its_api_terms() -> None:
    source = {source.id: source for source in load_sources()}["open_meteo"]
    assert source.verify.policy == "api_terms"
    assert source.access["limits"]["calls_per_hour"] == 5000


def test_index_weights_sum_to_one() -> None:
    config = load_index_config()
    assert abs(sum(config["ikr"]["weights"].values()) - 1.0) < 1e-9
    assert config["risk"]["base"] == 0.5


def test_thresholds_load() -> None:
    assert load_thresholds()["pm25_annual_ugm3"]["card_levels"] == [5, 10, 15, 25]
