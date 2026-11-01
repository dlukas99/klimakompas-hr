"""Features for the PM2.5 nowcast (SPEC §11). Only values known at the issue time may be lags."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 6, 12, 24)
LAGS = (1, 2, 3, 6, 12, 24)
WINDOWS = (3, 6, 24)
WEATHER = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "surface_pressure",
)
FEATURES = [
    "horizon",
    "station",
    "pm25_now",
    *[f"lag_{lag}" for lag in LAGS],
    *[f"mean_{window}" for window in WINDOWS],
    "hour",
    "weekday",
    "month",
    "heating_season",
    "holiday",
    *WEATHER,
    "cams_pm25",
]
HEATING_MONTHS = {10, 11, 12, 1, 2, 3, 4}
FIXED_HOLIDAYS = {
    (1, 1),
    (1, 6),
    (5, 1),
    (5, 30),
    (6, 22),
    (8, 5),
    (8, 15),
    (11, 1),
    (11, 18),
    (12, 25),
    (12, 26),
}


def easter(year: int) -> date:
    """Western Easter by the anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def is_holiday(day: date) -> bool:
    """Croatian public holidays, including Easter Monday and Corpus Christi."""
    if (day.month, day.day) in FIXED_HOLIDAYS:
        return True
    sunday = easter(day.year)
    return day in {sunday, sunday + timedelta(days=1), sunday + timedelta(days=60)}


def calendar_features(times: pd.DatetimeIndex) -> pd.DataFrame:
    local = times.tz_convert("Europe/Zagreb")
    return pd.DataFrame(
        {
            "hour": local.hour,
            "weekday": local.dayofweek,
            "month": local.month,
            "heating_season": local.month.isin(list(HEATING_MONTHS)).astype(int),
            "holiday": [int(is_holiday(item.date())) for item in local],
        },
        index=times,
    )


def history_features(pm25: pd.Series) -> pd.DataFrame:
    """Lags and means as known at each hour. `pm25` is hourly, with gaps as NaN."""
    frame = pd.DataFrame({"pm25_now": pm25})
    for lag in LAGS:
        frame[f"lag_{lag}"] = pm25.shift(lag)
    for window in WINDOWS:
        frame[f"mean_{window}"] = pm25.rolling(window, min_periods=max(1, window // 2)).mean()
    return frame


def build_samples(
    pm25: pd.Series, weather: pd.DataFrame, cams: pd.Series, station_code: int
) -> pd.DataFrame:
    """One row per (issue hour, horizon). Weather and CAMS are for the target hour."""
    index = pd.date_range(pm25.index.min(), pm25.index.max(), freq="h", tz="UTC")
    pm25 = pm25.reindex(index)
    history = history_features(pm25)
    frames = []
    for horizon in HORIZONS:
        target_time = index + pd.Timedelta(hours=horizon)
        rows = history.copy()
        rows["issued_at"] = index
        rows["target_time"] = target_time
        rows["horizon"] = horizon
        rows["station"] = station_code
        rows["y"] = pm25.reindex(target_time).to_numpy()
        rows["y_t24"] = pm25.reindex(target_time - pd.Timedelta(hours=24)).to_numpy()
        for name, values in calendar_features(target_time).items():
            rows[name] = values.to_numpy()
        for name in WEATHER:
            rows[name] = (
                weather[name].reindex(target_time).to_numpy() if name in weather else np.nan
            )
        rows["cams_pm25"] = cams.reindex(target_time).to_numpy()
        frames.append(rows)
    return pd.concat(frames, ignore_index=True)


def rolling_origin_splits(
    times: pd.Series, folds: int, test_days: int
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """(start, end) of each test window, newest last. Training uses only targets before start."""
    end = times.max()
    return [
        (
            end - pd.Timedelta(days=test_days * (folds - fold)),
            end - pd.Timedelta(days=test_days * (folds - fold - 1)),
        )
        for fold in range(folds)
    ]


def mae(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.mean(np.abs(y - yhat)))


def rmse(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y - yhat) ** 2)))
