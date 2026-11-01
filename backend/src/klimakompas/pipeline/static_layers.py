"""Batch builders for the flood and chronic air layers (SPEC §5.3)."""

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import structlog
from sqlalchemy import Connection

from klimakompas.core.db import upsert_rows
from klimakompas.pipeline.hazards import air_hazard, flood_eaf, flood_hazard, flood_monotonic
from klimakompas.pipeline.raster import (
    BOUNDS_WGS84,
    CellGrid,
    clip_wgs84,
    load_grid,
    nearest_fill,
    reduce_blocks,
    warped_to_grid,
)

log = structlog.get_logger()

FLOOD_PIXELS_PER_CELL = 10
AIR_GAP_FILL_CELLS = 3


def flood_paths(processed: Path, return_periods: list[int]) -> dict[int, Path]:
    return {rp: processed / "flood" / f"rp{rp}_depth.tif" for rp in return_periods}


def clip_flood(
    source: dict[str, Any], processed: Path, return_periods: list[int]
) -> dict[int, Path]:
    base = source["access"]["base_url"]
    return {
        rp: clip_wgs84(f"/vsicurl/{base}Europe_RP{rp}_filled_depth.tif", path, BOUNDS_WGS84)
        for rp, path in flood_paths(processed, return_periods).items()
    }


def _flooded_share(path: Path, grid: CellGrid, threshold: float, strict: bool) -> np.ndarray:
    def reducer(block: np.ndarray) -> np.ndarray:
        # Nodata is a large negative value, so it never counts as flooded.
        flooded = block > threshold if strict else block >= threshold
        result: np.ndarray = flooded.mean(axis=(2, 3))
        return result

    with (
        rasterio.open(path) as dataset,
        warped_to_grid(dataset, grid, FLOOD_PIXELS_PER_CELL) as vrt,
    ):
        return grid.pick(reduce_blocks(vrt, grid, FLOOD_PIXELS_PER_CELL, reducer))


def build_flood(
    conn: Connection, paths: dict[int, Path], config: dict[str, Any], version: str
) -> int:
    grid = load_grid(conn)
    threshold = float(config["depth_threshold_m"])
    s10_raw = _flooded_share(paths[10], grid, threshold, strict=True)
    s100_raw = _flooded_share(paths[100], grid, threshold, strict=True)
    s500_raw = _flooded_share(paths[500], grid, threshold, strict=True)
    deep = _flooded_share(paths[100], grid, float(config["deep_threshold_m"]), strict=False)
    s10, s100, s500 = flood_monotonic(s10_raw, s100_raw, s500_raw)
    eaf = flood_eaf(s10, s100, s500)
    hazard = flood_hazard(eaf, float(config["eaf_ref"]))
    return upsert_rows(
        conn,
        "haz.flood_cell",
        (
            "cell_id",
            "s_rp10",
            "s_rp100",
            "s_rp500",
            "s_deep_rp100",
            "eaf",
            "h_flood",
            "source_version",
        ),
        ("cell_id",),
        zip(
            grid.cell_ids,
            s10.tolist(),
            s100.tolist(),
            s500.tolist(),
            deep.tolist(),
            eaf.tolist(),
            hazard.tolist(),
            [version] * grid.size,
            strict=True,
        ),
    )


def read_pm25(path: str, grid: CellGrid) -> np.ndarray:
    """The EEA raster shares the INSPIRE 1 km grid, so one pixel is one cell."""
    with rasterio.open(path) as dataset, warped_to_grid(dataset, grid, 1) as vrt:
        data = vrt.read(1, masked=True).astype(float).filled(np.nan)
    data[data < 0] = np.nan
    return grid.pick(data)


def build_air(
    conn: Connection, source_path: str, config: dict[str, Any], year: int
) -> tuple[int, int, int]:
    """Return (rows, gap-filled cells, cells still empty)."""
    grid = load_grid(conn)
    raw = read_pm25(source_path, grid)
    filled = nearest_fill(raw, grid, AIR_GAP_FILL_CELLS)
    hazard = air_hazard(filled, float(config["zero_at_ugm3"]), float(config["one_at_ugm3"]))

    def clean(values: np.ndarray) -> list[float | None]:
        return [None if np.isnan(value) else float(value) for value in values]

    gap = np.isnan(raw) & ~np.isnan(filled)
    rows = upsert_rows(
        conn,
        "haz.air_cell",
        ("cell_id", "pm25_annual", "year", "h_air", "gap_filled"),
        ("cell_id",),
        zip(
            grid.cell_ids,
            clean(filled),
            [year] * grid.size,
            clean(hazard),
            gap.tolist(),
            strict=True,
        ),
    )
    return rows, int(gap.sum()), int(np.isnan(filled).sum())
