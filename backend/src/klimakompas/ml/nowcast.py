"""Backfill, training, validation and hourly forecast for the PM2.5 nowcast (SPEC §11)."""

import json
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import lightgbm as lgb
import numpy as np
import pandas as pd
import structlog
from sqlalchemy import Connection, Engine, text

from klimakompas.core.config import ROOT, load_sources
from klimakompas.core.db import upsert_rows
from klimakompas.core.http import HttpClient
from klimakompas.live.connectors import AZO_BASE, AZO_HOURLY, AZO_MIN_INTERVAL_S
from klimakompas.live.parsers import parse_aq
from klimakompas.ml.features import (
    FEATURES,
    HORIZONS,
    WEATHER,
    build_samples,
    calendar_features,
    history_features,
    mae,
    rmse,
    rolling_origin_splits,
)

log = structlog.get_logger()

PM25 = "28"
HISTORY_DAYS = 730
MIN_STATION_HOURS = 2000
BACKFILL_CHUNK_DAYS = 60
MODEL_DIR = ROOT / "data" / "processed" / "ml"
RESULTS_PATH = ROOT / "docs" / "ml-rezultati.json"
FOLDS = 3
TEST_DAYS = 30
PARAMS: dict[str, Any] = {
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "verbose": -1,
    "n_jobs": 8,
}
QUANTILES = {"lo": 0.1, "hi": 0.9}
MODEL_VERSION = "lgbm-1"
FORECAST_FRESH_HOURS = 3


def _open_meteo(key: str) -> str:
    source = next(item for item in load_sources() if item.id == "open_meteo")
    url: str = source.access[key]
    return url


def stations_with_pm25(conn: Connection, min_hours: int = 0) -> list[Any]:
    return list(
        conn.execute(
            text(
                """
                SELECT s.station_id, s.name, ST_Y(ST_Transform(s.geom, 4326)) AS lat,
                       ST_X(ST_Transform(s.geom, 4326)) AS lon, count(o.ts) AS hours
                FROM live.aq_stations s
                JOIN live.aq_obs o ON o.station_id = s.station_id AND o.pollutant_id = :pollutant
                WHERE s.geom IS NOT NULL
                GROUP BY 1, 2, 3, 4
                HAVING count(o.ts) >= :min_hours
                ORDER BY s.station_id
                """
            ),
            {"pollutant": PM25, "min_hours": min_hours},
        )
    )


def backfill_station(client: HttpClient, engine: Engine, station_id: str, today: date) -> int:
    """Fetch two years of hourly PM2.5 in chunks, spaced as the AZO service requires."""
    total = 0
    start = today - timedelta(days=HISTORY_DAYS)
    while start < today:
        end = min(start + timedelta(days=BACKFILL_CHUNK_DAYS), today)
        threading.Event().wait(AZO_MIN_INTERVAL_S)
        url = (
            f"{AZO_BASE}/podatak/export/json?postaja={station_id}&polutant={PM25}"
            f"&tipPodatka={AZO_HOURLY}&vrijemeOd={start:%d.%m.%Y}&vrijemeDo={end:%d.%m.%Y}"
        )
        response = client.get(url)
        if response.is_success:
            observations = parse_aq(response.json())
            with engine.begin() as conn:
                total += upsert_rows(
                    conn,
                    "live.aq_obs",
                    ("station_id", "pollutant_id", "ts", "value", "unit"),
                    ("station_id", "pollutant_id", "ts"),
                    ((station_id, PM25, o.ts, o.value, o.unit) for o in observations),
                )
        start = end
    return total


def _hourly_frame(body: dict[str, Any]) -> pd.DataFrame:
    hourly = body["hourly"]
    index = pd.to_datetime(hourly["time"], utc=True)
    return pd.DataFrame({k: v for k, v in hourly.items() if k != "time"}, index=index)


def _cached_json(client: HttpClient, url: str, params: dict[str, Any], cache: Path) -> Any:
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    response = client.request("GET", url, params=params, timeout=120.0)
    response.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(response.text, encoding="utf-8")
    return response.json()


def weather_history(
    client: HttpClient, station: Any, start: date, end: date, folder: Path
) -> tuple[pd.DataFrame, pd.Series]:
    """Open-Meteo weather and CAMS PM2.5 for one point. Cached, so the API limits are respected."""
    weather = _cached_json(
        client,
        _open_meteo("archive"),
        {
            "latitude": station.lat,
            "longitude": station.lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(WEATHER),
            "timezone": "GMT",
        },
        folder / f"weather_{station.station_id}.json",
    )
    cams = _cached_json(
        client,
        _open_meteo("air_quality"),
        {
            "latitude": station.lat,
            "longitude": station.lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": "pm2_5",
            "timezone": "GMT",
        },
        folder / f"cams_{station.station_id}.json",
    )
    return _hourly_frame(weather), _hourly_frame(cams)["pm2_5"]


def _station_series(conn: Connection, station_id: str) -> pd.Series:
    rows = conn.execute(
        text(
            "SELECT ts, value FROM live.aq_obs "
            "WHERE station_id = :id AND pollutant_id = :pollutant ORDER BY ts"
        ),
        {"id": station_id, "pollutant": PM25},
    ).all()
    index = pd.to_datetime([row.ts for row in rows], utc=True)
    return pd.Series([row.value for row in rows], index=index, dtype=float).sort_index()


def build_dataset(
    conn: Connection, client: HttpClient, folder: Path
) -> tuple[pd.DataFrame, dict[str, int]]:
    stations = stations_with_pm25(conn, MIN_STATION_HOURS)
    codes = {station.station_id: code for code, station in enumerate(stations)}
    today = datetime.now(UTC).date()
    start = today - timedelta(days=HISTORY_DAYS)
    frames = []
    for station in stations:
        pm25 = _station_series(conn, station.station_id)
        pm25 = pm25[~pm25.index.duplicated()]
        weather, cams = weather_history(client, station, start, today - timedelta(days=7), folder)
        samples = build_samples(pm25, weather, cams, codes[station.station_id])
        samples["station_id"] = station.station_id
        frames.append(samples.dropna(subset=["y", "pm25_now"]))
        log.info("station samples", station=station.name, rows=len(frames[-1]))
    return pd.concat(frames, ignore_index=True), codes


def _fit(train: pd.DataFrame, **extra: Any) -> lgb.LGBMRegressor:
    model = lgb.LGBMRegressor(**PARAMS, **extra)
    model.fit(train[FEATURES], train["y"], categorical_feature=["station"])
    return model


def evaluate(samples: pd.DataFrame) -> dict[str, Any]:
    """Rolling-origin validation. Training keeps only targets before the test window begins."""
    splits = rolling_origin_splits(samples["target_time"], FOLDS, TEST_DAYS)
    parts = []
    for start, end in splits:
        train = samples[samples["target_time"] < start]
        test = samples[(samples["issued_at"] >= start) & (samples["target_time"] <= end)].copy()
        if train.empty or test.empty:
            continue
        test["yhat"] = _fit(train).predict(test[FEATURES])
        test["lo"] = _fit(train, objective="quantile", alpha=QUANTILES["lo"]).predict(
            test[FEATURES]
        )
        test["hi"] = _fit(train, objective="quantile", alpha=QUANTILES["hi"]).predict(
            test[FEATURES]
        )
        parts.append(test)
        log.info("fold done", start=str(start), rows=len(test))
    results = pd.concat(parts, ignore_index=True)

    def scores(frame: pd.DataFrame) -> dict[str, float | int | None]:
        y = frame["y"].to_numpy()
        model = frame["yhat"].to_numpy()
        persistence = frame["pm25_now"].to_numpy()
        t24 = frame[frame["y_t24"].notna()]
        cams = frame[frame["cams_pm25"].notna()]
        model_mae = mae(y, model)
        persistence_mae = mae(y, persistence)
        return {
            "n": len(frame),
            "mae": round(model_mae, 3),
            "rmse": round(rmse(y, model), 3),
            "mae_persistence": round(persistence_mae, 3),
            "mae_t24": round(mae(t24["y"].to_numpy(), t24["y_t24"].to_numpy()), 3)
            if len(t24)
            else None,
            "mae_cams": round(mae(cams["y"].to_numpy(), cams["cams_pm25"].to_numpy()), 3)
            if len(cams)
            else None,
            "mae_model_on_cams_rows": round(mae(cams["y"].to_numpy(), cams["yhat"].to_numpy()), 3)
            if len(cams)
            else None,
            "skill_vs_persistence": round(1 - model_mae / persistence_mae, 3)
            if persistence_mae
            else None,
            "coverage_80": round(float(((y >= frame["lo"]) & (y <= frame["hi"])).mean()), 3),
        }

    return {
        "overall": scores(results),
        "by_horizon": {
            str(horizon): scores(group) for horizon, group in results.groupby("horizon")
        },
        "by_station": {
            str(station): scores(group) for station, group in results.groupby("station_id")
        },
        "folds": [[str(start), str(end)] for start, end in splits],
    }


def train(engine: Engine, client: HttpClient) -> dict[str, Any]:
    folder = ROOT / "data" / "raw" / "open_meteo" / "history"
    with engine.connect() as conn:
        samples, codes = build_dataset(conn, client, folder)
    metrics = evaluate(samples)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, extra in (
        ("point", {}),
        ("lo", {"objective": "quantile", "alpha": QUANTILES["lo"]}),
        ("hi", {"objective": "quantile", "alpha": QUANTILES["hi"]}),
    ):
        _fit(samples, **extra).booster_.save_model(str(MODEL_DIR / f"pm25_{name}.txt"))
    (MODEL_DIR / "stations.json").write_text(json.dumps(codes), encoding="utf-8")
    overall = metrics["overall"]
    # SPEC §11: if the model does not beat CAMS on validation, CAMS is what gets shown.
    beats_cams = overall["mae_cams"] is None or (
        overall["mae_model_on_cams_rows"] < overall["mae_cams"]
    )
    metrics["serve_model"] = bool(beats_cams)
    metrics["stations"] = len(codes)
    metrics["features"] = FEATURES
    metrics["trained_at"] = datetime.now(UTC).isoformat()
    RESULTS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ml.models (model_version, trained_at, params, metrics, artifact_path) "
                "VALUES (:version, :trained, CAST(:params AS jsonb), CAST(:metrics AS jsonb), "
                ":path) "
                "ON CONFLICT (model_version) DO UPDATE SET trained_at = EXCLUDED.trained_at, "
                "params = EXCLUDED.params, metrics = EXCLUDED.metrics"
            ),
            {
                "version": MODEL_VERSION,
                "trained": datetime.now(UTC),
                "params": json.dumps(PARAMS),
                "metrics": json.dumps(metrics),
                "path": str(MODEL_DIR.relative_to(ROOT)),
            },
        )
    return metrics


def _forecast_frames(
    client: HttpClient, stations: list[Any]
) -> dict[str, tuple[pd.DataFrame, pd.Series]]:
    """Weather and CAMS forecasts in one request per service, for all stations at once."""
    common = {
        "latitude": ",".join(str(station.lat) for station in stations),
        "longitude": ",".join(str(station.lon) for station in stations),
        "forecast_days": 2,
        "timezone": "GMT",
    }
    weather = client.request(
        "GET", _open_meteo("forecast"), params={**common, "hourly": ",".join(WEATHER)}
    )
    cams = client.request("GET", _open_meteo("air_quality"), params={**common, "hourly": "pm2_5"})
    weather.raise_for_status()
    cams.raise_for_status()

    def listed(body: Any) -> list[dict[str, Any]]:
        return body if isinstance(body, list) else [body]

    result = {}
    for station, one_weather, one_cams in zip(
        stations, listed(weather.json()), listed(cams.json()), strict=True
    ):
        result[station.station_id] = (_hourly_frame(one_weather), _hourly_frame(one_cams)["pm2_5"])
    return result


def forecast_rows(
    pm25: pd.Series,
    weather: pd.DataFrame,
    cams: pd.Series,
    station_code: int,
    issued_at: pd.Timestamp,
) -> pd.DataFrame:
    """Feature rows for each horizon from the latest hour with data."""
    index = pd.date_range(issued_at - pd.Timedelta(hours=48), issued_at, freq="h", tz="UTC")
    history = history_features(pm25.reindex(index)).iloc[[-1]]
    rows = []
    for horizon in HORIZONS:
        target = issued_at + pd.Timedelta(hours=horizon)
        row: dict[str, Any] = history.iloc[0].to_dict()
        row |= {"horizon": horizon, "station": station_code, "target_time": target}
        row |= calendar_features(pd.DatetimeIndex([target])).iloc[0].to_dict()
        for name in WEATHER:
            row[name] = weather[name].get(target, np.nan) if name in weather else np.nan
        row["cams_pm25"] = cams.get(target, np.nan)
        rows.append(row)
    return pd.DataFrame(rows)


def predict(engine: Engine, client: HttpClient) -> int:
    """Hourly job. A station without fresh values simply gets no new forecast."""
    point_path = MODEL_DIR / "pm25_point.txt"
    if not point_path.exists() or not RESULTS_PATH.exists():
        log.info("no model yet")
        return 0
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    serve_model = bool(results["serve_model"])
    codes: dict[str, int] = json.loads((MODEL_DIR / "stations.json").read_text(encoding="utf-8"))
    point = lgb.Booster(model_file=str(point_path))
    low = lgb.Booster(model_file=str(MODEL_DIR / "pm25_lo.txt"))
    high = lgb.Booster(model_file=str(MODEL_DIR / "pm25_hi.txt"))
    with engine.connect() as conn:
        stations = [s for s in stations_with_pm25(conn) if s.station_id in codes]
        series = {s.station_id: _station_series(conn, s.station_id) for s in stations}
    now = pd.Timestamp.now(tz="UTC").floor("h")
    fresh = [
        s
        for s in stations
        if len(series[s.station_id])
        and now - series[s.station_id].index.max() <= pd.Timedelta(hours=FORECAST_FRESH_HOURS)
    ]
    if not fresh:
        return 0
    try:
        frames = _forecast_frames(client, fresh)
    except httpx.HTTPError as error:
        log.warning("forecast inputs unavailable", error=type(error).__name__)
        return 0
    rows: list[tuple[Any, ...]] = []
    issued = datetime.now(UTC)
    for station in fresh:
        pm25 = series[station.station_id]
        weather, cams = frames[station.station_id]
        frame = forecast_rows(pm25, weather, cams, codes[station.station_id], pm25.index.max())
        features = frame[FEATURES].astype(float)
        if serve_model:
            yhat = np.maximum(point.predict(features), 0)
            lo = np.maximum(low.predict(features), 0)
            hi = np.maximum(high.predict(features), 0)
            version = MODEL_VERSION
        else:
            yhat = frame["cams_pm25"].to_numpy(dtype=float)
            lo = hi = [None] * len(yhat)
            version = "cams"
        for target, value, lower, upper in zip(frame["target_time"], yhat, lo, hi, strict=True):
            if not np.isnan(value):
                rows.append(
                    (
                        station.station_id,
                        issued,
                        target.to_pydatetime(),
                        float(value),
                        None if lower is None else float(lower),
                        None if upper is None else float(upper),
                        version,
                    )
                )
    with engine.begin() as conn:
        count = upsert_rows(
            conn,
            "ml.pm25_forecast",
            ("station_id", "issued_at", "target_ts", "yhat", "lo", "hi", "model_version"),
            ("station_id", "issued_at", "target_ts"),
            rows,
        )
        conn.execute(
            text("DELETE FROM ml.pm25_forecast WHERE issued_at < now() - interval '7 days'")
        )
    return count
