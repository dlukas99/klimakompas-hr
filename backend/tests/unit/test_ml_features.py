from datetime import date

import numpy as np
import pandas as pd
import pytest

from klimakompas.ml.features import (
    FEATURES,
    build_samples,
    calendar_features,
    easter,
    history_features,
    is_holiday,
    rolling_origin_splits,
)


def series(hours: int = 72) -> pd.Series:
    index = pd.date_range("2026-01-10 00:00", periods=hours, freq="h", tz="UTC")
    return pd.Series(np.arange(hours, dtype=float), index=index)


def test_lags_use_only_past_values() -> None:
    frame = history_features(series())
    assert frame.loc[frame.index[30], "pm25_now"] == 30
    assert frame.loc[frame.index[30], "lag_1"] == 29
    assert frame.loc[frame.index[30], "lag_24"] == 6
    assert frame.loc[frame.index[30], "mean_3"] == 29


def test_samples_have_no_target_leakage() -> None:
    pm25 = series()
    samples = build_samples(pm25, pd.DataFrame(index=pm25.index), pd.Series(dtype=float), 0)
    row = samples[(samples["issued_at"] == pm25.index[30]) & (samples["horizon"] == 6)].iloc[0]
    assert row["y"] == 36
    assert row["pm25_now"] == 30
    assert row["y_t24"] == 12
    # Every feature comes from the issue time or earlier, except calendar and forecast inputs.
    assert row["lag_1"] < row["pm25_now"] < row["y"]


def test_weather_and_cams_are_taken_at_the_target_hour() -> None:
    pm25 = series()
    weather = pd.DataFrame({"temperature_2m": np.arange(72.0) * 10}, index=pm25.index)
    cams = pd.Series(np.arange(72.0) * 100, index=pm25.index)
    samples = build_samples(pm25, weather, cams, 0)
    row = samples[(samples["issued_at"] == pm25.index[10]) & (samples["horizon"] == 3)].iloc[0]
    assert row["temperature_2m"] == 130
    assert row["cams_pm25"] == 1300


def test_all_features_are_built() -> None:
    pm25 = series()
    samples = build_samples(pm25, pd.DataFrame(index=pm25.index), pd.Series(dtype=float), 0)
    assert set(FEATURES) <= set(samples.columns)


def test_gaps_stay_gaps() -> None:
    pm25 = series().drop(series().index[20])
    frame = build_samples(pm25, pd.DataFrame(index=pm25.index), pd.Series(dtype=float), 0)
    row = frame[(frame["issued_at"] == series().index[21]) & (frame["horizon"] == 1)].iloc[0]
    assert np.isnan(row["lag_1"])


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 11, 1), True),
        (date(2026, 11, 18), True),
        (date(2026, 4, 6), True),
        (date(2026, 6, 4), True),
        (date(2026, 11, 2), False),
    ],
)
def test_croatian_holidays(day: date, expected: bool) -> None:
    assert is_holiday(day) is expected


def test_easter_dates() -> None:
    assert easter(2026) == date(2026, 4, 5)
    assert easter(2025) == date(2025, 4, 20)


def test_calendar_uses_local_time() -> None:
    times = pd.DatetimeIndex(["2026-01-15 23:30:00+00:00"])
    frame = calendar_features(times)
    assert frame["hour"].iloc[0] == 0
    assert frame["heating_season"].iloc[0] == 1


def test_rolling_origin_windows_are_ordered_and_contiguous() -> None:
    times = pd.Series(pd.date_range("2026-01-01", "2026-12-31", freq="D", tz="UTC"))
    splits = rolling_origin_splits(times, 3, 30)
    assert len(splits) == 3
    assert splits[0][1] == splits[1][0]
    assert splits[-1][1] == times.max()
