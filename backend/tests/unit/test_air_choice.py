"""ADR 0004: what the card shows when the local station has no fresh PM2.5."""

from typing import Any

from klimakompas.api.data import choose_air_now


def station(
    identifier: str, lat: float, lon: float, pm25: bool | None = None, pm10: bool | None = None
) -> dict[str, Any]:
    def value(fresh: bool) -> dict[str, Any]:
        return {"value": 1.0, "stale": not fresh, "observed_at": "2026-11-01T00:00:00Z"}

    values = {}
    if pm25 is not None:
        values["pm25"] = value(pm25)
    if pm10 is not None:
        values["pm10"] = value(pm10)
    return {"id": identifier, "name": identifier, "lat": lat, "lon": lon, "values": values}


OSIJEK = (45.55, 18.69)
NEAR = (45.56, 18.70)
FAR = (45.16, 18.01)


def test_prefers_local_pm25() -> None:
    chosen = choose_air_now([station("a", *NEAR, pm25=True, pm10=True)], *OSIJEK, 15)
    assert chosen is not None
    assert (chosen["pollutant"], chosen["substitution"]) == ("pm25", "local")


def test_local_pm10_comes_before_a_distant_pm25() -> None:
    stations = [station("near", *NEAR, pm10=True), station("far", *FAR, pm25=True)]
    chosen = choose_air_now(stations, *OSIJEK, 15)
    assert chosen is not None
    assert chosen["station"]["id"] == "near"
    assert (chosen["pollutant"], chosen["substitution"]) == ("pm10", "local_pm10")


def test_falls_back_to_the_nearest_fresh_pm25_with_distance() -> None:
    chosen = choose_air_now([station("far", *FAR, pm25=True)], *OSIJEK, 15)
    assert chosen is not None
    assert chosen["substitution"] == "nearest_pm25"
    assert chosen["station"]["distance_km"] > 15


def test_stale_values_do_not_count() -> None:
    assert choose_air_now([station("a", *NEAR, pm25=False, pm10=False)], *OSIJEK, 15) is None
