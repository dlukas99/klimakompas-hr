"""Connectors for the batch hazard layers. Each run is logged in meta like any other source."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from pyproj import Transformer
from sqlalchemy import text

from klimakompas.core.config import get_settings, load_crosswalk, load_index_config, load_sources
from klimakompas.core.db import upsert_rows
from klimakompas.core.raw import save_raw
from klimakompas.live.parsers import parse_k1_hot_days
from klimakompas.pipeline.hazards import (
    fire_hazard,
    heat_hazard,
    robust_minmax,
    station_corrected,
)
from klimakompas.pipeline.raster import (
    BOUNDS_WGS84,
    CELL_M,
    CellGrid,
    configure_gdal,
    load_grid,
)
from klimakompas.pipeline.satellite import (
    burnt_years,
    landcover_shares,
    landsat_median,
    lst_delta,
    worldcover_counts,
)
from klimakompas.pipeline.static_layers import build_air, build_flood, clip_flood
from klimakompas.sources.base import (
    LoadResult,
    RunContext,
    control,
    mark_source_used,
    record,
)
from klimakompas.sources.ecde import (
    REQUESTS,
    climatology,
    extract_netcdf,
    fetch_indicator,
    interpolate_points,
    interpolate_to_cells,
)

log = structlog.get_logger()

FLOOD_VERSION = "3.1.1"
PM25_YEAR = 2023


def _config() -> dict[str, Any]:
    hazards: dict[str, Any] = load_index_config()["hazards"]
    return hazards


def _interim(ctx: RunContext) -> Path:
    return ctx.data_dir / "interim"


def _optional(values: np.ndarray) -> list[float | None]:
    return [None if np.isnan(value) else float(value) for value in values]


class FloodConnector:
    source_id = "jrc_efas_flood"

    def fetch(self, ctx: RunContext) -> list[Path]:
        configure_gdal(ctx.client.user_agent)
        paths = clip_flood(
            ctx.source.model_dump(),
            ctx.data_dir / "processed",
            _config()["flood"]["return_periods"],
        )
        return list(paths.values())

    def parse(self, artifacts: list[Path]) -> list[Path]:
        return artifacts

    def load(self, frame: list[Path], ctx: RunContext) -> LoadResult:
        config = _config()["flood"]
        paths = dict(zip(config["return_periods"], frame, strict=True))
        rows = build_flood(ctx.db, paths, config, FLOOD_VERSION)
        peak = ctx.db.execute(text("SELECT max(h_flood) FROM haz.flood_cell")).scalar_one()
        control(ctx, "h_flood_max", peak, 1.0)
        return LoadResult(rows=rows)


class AirConnector:
    source_id = "eea_pm25_1km"

    def fetch(self, ctx: RunContext) -> list[Path]:
        configure_gdal(ctx.client.user_agent)
        return []

    def parse(self, artifacts: list[Path]) -> list[Path]:
        return artifacts

    def load(self, frame: list[Path], ctx: RunContext) -> LoadResult:
        url = f"/vsicurl/{ctx.source.access['urls'][0]}"
        rows, gap_filled, empty = build_air(ctx.db, url, _config()["air"], PM25_YEAR)
        record(ctx, "air_gap_filled_cells", gap_filled)
        record(ctx, "air_empty_cells", empty)
        low, high = ctx.db.execute(
            text("SELECT min(pm25_annual), max(pm25_annual) FROM haz.air_cell")
        ).one()
        control(ctx, "pm25_in_range", float(0 <= low and high <= 1000), 1)
        return LoadResult(rows=rows)


class WorldCoverConnector:
    source_id = "esa_worldcover"

    def fetch(self, ctx: RunContext) -> list[Path]:
        configure_gdal(ctx.client.user_agent)
        return []

    def parse(self, artifacts: list[Path]) -> list[Path]:
        return artifacts

    def load(self, frame: list[Path], ctx: RunContext) -> LoadResult:
        grid = load_grid(ctx.db)
        counts = worldcover_counts(ctx.client, grid, _interim(ctx) / "worldcover_counts.npz")
        shares = landcover_shares(counts, grid, _config()["fire"]["fuel_classes"])
        rows = upsert_rows(
            ctx.db,
            "haz.landcover_cell",
            ("cell_id", "tree_share", "builtup_share", "water_share", "fuel_share"),
            ("cell_id",),
            zip(
                grid.cell_ids,
                shares["tree_share"].tolist(),
                shares["builtup_share"].tolist(),
                shares["water_share"].tolist(),
                shares["fuel_share"].tolist(),
                strict=True,
            ),
        )
        return LoadResult(rows=rows)


class LandsatConnector:
    """Fills the LST cache that the ECDE connector turns into the heat layer."""

    source_id = "landsat_lst"

    def fetch(self, ctx: RunContext) -> list[Path]:
        configure_gdal(ctx.client.user_agent)
        return []

    def parse(self, artifacts: list[Path]) -> list[Path]:
        return artifacts

    def load(self, frame: list[Path], ctx: RunContext) -> LoadResult:
        grid = load_grid(ctx.db)
        median = landsat_median(
            ctx.client, grid, _config()["heat"]["lst"], _interim(ctx) / "landsat"
        )
        np.save(_interim(ctx) / "lst_median.npy", median)
        record(ctx, "lst_cells_without_value", float(np.isnan(median).sum()))
        return LoadResult(rows=int((~np.isnan(median)).sum()))


class BurntConnector:
    source_id = "burnt_areas"

    def fetch(self, ctx: RunContext) -> list[Path]:
        configure_gdal(ctx.client.user_agent)
        return []

    def parse(self, artifacts: list[Path]) -> list[Path]:
        return artifacts

    def load(self, frame: list[Path], ctx: RunContext) -> LoadResult:
        grid = load_grid(ctx.db)
        years = burnt_years(ctx.client, grid, _config()["fire"]["burnt"], _interim(ctx) / "burnt")
        np.save(_interim(ctx) / "burnt_years.npy", years)
        return LoadResult(rows=int((years > 0).sum()))


def _corrected_hot_days(
    ctx: RunContext, field: Any, grid: CellGrid, config: dict[str, Any]
) -> np.ndarray:
    """ERA5 hot days corrected with DHMZ station counts (ADR 0006).

    The 25 km grid averages coastal towns with the mountains behind them, so Split gets 2 hot days
    a year where its station records about 44.
    """
    climate = next(entry for entry in load_sources() if entry.id == "dhmz_climate")
    template = climate.access["stations"]
    stations = load_crosswalk("dhmz_k1_stations")["stations"]
    rows = ctx.db.execute(
        text(
            """
            SELECT DISTINCT ON (n.name) n.name, ST_X(n.point) AS x, ST_Y(n.point) AS y
            FROM ref.naselja n LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code
            WHERE n.name = ANY(:names)
            ORDER BY n.name, p.pop_total DESC NULLS LAST
            """
        ),
        {"names": [item["naselje"] for item in stations.values()]},
    )
    points = {row.name: (row.x, row.y) for row in rows}
    observed, xs, ys = [], [], []
    for slug, item in stations.items():
        response = ctx.client.get(template.format(station=slug))
        response.raise_for_status()
        save_raw(ctx.data_dir, climate.id, f"{slug}.xml", response, climate.license)
        observed.append(parse_k1_hot_days(response.content))
        x, y = points[item["naselje"]]
        xs.append(x)
        ys.append(y)
    x = np.array(xs)
    y = np.array(ys)
    lon, lat = Transformer.from_crs(3035, 4326, always_xy=True).transform(x, y)
    at_stations = interpolate_points(field, np.asarray(lon), np.asarray(lat))
    target_x = np.asarray(grid.x_min + (grid.cols + 0.5) * CELL_M, dtype=np.float64)
    target_y = np.asarray(grid.y_max - (grid.rows + 0.5) * CELL_M, dtype=np.float64)
    corrected, loo_mae, raw_mae = station_corrected(
        interpolate_to_cells(field, ctx.db, grid),
        target_x,
        target_y,
        x,
        y,
        at_stations,
        np.array(observed),
        int(config["neighbours"]),
        float(config["max_km"]) * 1000,
    )
    mark_source_used(ctx.db, climate.id, len(observed))
    record(ctx, "hot_days_mae_grid_only", raw_mae)
    record(ctx, "hot_days_mae_leave_one_out", loo_mae)
    return corrected


def _populated_mask(ctx: RunContext, grid: CellGrid) -> np.ndarray:
    populated = set(
        ctx.db.execute(text("SELECT cell_id FROM pop.grid_2021 WHERE pop_total > 0")).scalars()
    )
    return np.array([cell in populated for cell in grid.cell_ids])


class EcdeConnector:
    """Heat and fire layers, which combine ECDE with the satellite layers built before it."""

    source_id = "ecde"

    def fetch(self, ctx: RunContext) -> list[Path]:
        folder = _latest_folder(ctx)
        return [fetch_indicator(get_settings(), name, folder) for name in REQUESTS]

    def parse(self, artifacts: list[Path]) -> list[Path]:
        return artifacts

    def load(self, frame: list[Path], ctx: RunContext) -> LoadResult:
        config = _config()
        normal = load_index_config()["normalization"]
        low, high = float(normal["lower_pct"]), float(normal["upper_pct"])
        first, last = (int(part) for part in str(config["heat"]["reference_period"]).split("-"))
        grid = load_grid(ctx.db)
        mask = _populated_mask(ctx, grid)
        lookup = dict(zip(REQUESTS, frame, strict=True))

        def field(name: str) -> Any:
            path = lookup[name]
            netcdf = extract_netcdf(path, path.with_name(f"{name}_nc"))
            return climatology(netcdf, first, last, BOUNDS_WGS84)

        hot = _corrected_hot_days(ctx, field("hot_days"), grid, config["heat"]["hot_days_stations"])
        tropical = interpolate_to_cells(field("tropical_nights"), ctx.db, grid)
        fwi = interpolate_to_cells(field("fwi_days"), ctx.db, grid)

        rows = {
            row.cell_id: row
            for row in ctx.db.execute(
                text(
                    "SELECT cell_id, tree_share, builtup_share, water_share, fuel_share "
                    "FROM haz.landcover_cell"
                )
            )
        }
        tree = np.array([rows[cell].tree_share for cell in grid.cell_ids])
        built = np.array([rows[cell].builtup_share for cell in grid.cell_ids])
        water = np.array([rows[cell].water_share for cell in grid.cell_ids])
        fuel = np.array([rows[cell].fuel_share for cell in grid.cell_ids])

        lst_path = _interim(ctx) / "lst_median.npy"
        lst = np.load(lst_path) if lst_path.exists() else None
        lst_config = config["heat"]["lst"]
        delta = (
            lst_delta(
                lst,
                built,
                water,
                grid,
                float(lst_config["rural_builtup_max"]),
                float(lst_config["neighbourhood_km"]),
            )
            if lst is not None
            else None
        )

        def rn(values: np.ndarray) -> np.ndarray:
            return robust_minmax(values, values[mask], low, high)

        heat = heat_hazard(
            rn(hot),
            rn(tropical),
            rn(delta) if delta is not None else None,
            config["heat"]["weights"],
        )
        missing = np.full(grid.size, np.nan)
        rows_heat = upsert_rows(
            ctx.db,
            "haz.heat_cell",
            (
                "cell_id",
                "hot_days",
                "tropical_nights",
                "lst_median_c",
                "lst_delta_c",
                "tree_share",
                "builtup_share",
                "h_heat",
            ),
            ("cell_id",),
            zip(
                grid.cell_ids,
                hot.tolist(),
                tropical.tolist(),
                _optional(lst if lst is not None else missing),
                _optional(delta if delta is not None else missing),
                tree.tolist(),
                built.tolist(),
                _optional(heat),
                strict=True,
            ),
        )

        fire_config = config["fire"]
        burnt_path = _interim(ctx) / "burnt_years.npy"
        burnt = np.load(burnt_path) if burnt_path.exists() else np.zeros(grid.size)
        weights = fire_config["weights"]
        fire_weight = float(weights["fwi_x_fuel"])
        burnt_weight = float(weights["burnt_history"])
        if not burnt_path.exists():
            fire_weight, burnt_weight = 1.0, 0.0
        fire = fire_hazard(
            rn(fwi), fuel, rn(burnt), fire_weight, burnt_weight, float(fire_config["fuel_floor"])
        )
        upsert_rows(
            ctx.db,
            "haz.fire_cell",
            ("cell_id", "fwi_days", "fuel_share", "burnt_years_2km", "h_fire"),
            ("cell_id",),
            zip(
                grid.cell_ids,
                fwi.tolist(),
                fuel.tolist(),
                [int(value) for value in burnt.tolist()],
                _optional(fire),
                strict=True,
            ),
        )
        record(ctx, "lst_available", float(lst is not None))
        record(ctx, "burnt_history_available", float(burnt_path.exists()))
        control(ctx, "heat_in_range", float(np.nanmin(heat) >= 0 and np.nanmax(heat) <= 1), 1)
        control(ctx, "fire_in_range", float(np.nanmin(fire) >= 0 and np.nanmax(fire) <= 1), 1)
        return LoadResult(rows=rows_heat)


def _latest_folder(ctx: RunContext) -> Path:
    base = ctx.data_dir / "raw" / "ecde"
    existing = sorted(path.parent for path in base.glob("*/hot_days.zip"))
    return existing[-1] if existing else base / datetime.now(UTC).date().isoformat()
