"""Windowed raster helpers on the INSPIRE 1 km grid. Rasters are never read whole."""

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from numpy.typing import NDArray
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds
from sqlalchemy import Connection, text

from klimakompas.pipeline.grid import parse_cell_id

CELL_M = 1000
BLOCK_CELLS = 100
# West, south, east, north with a margin around Croatia, for sources in WGS84.
BOUNDS_WGS84 = (13.3, 42.2, 19.6, 46.7)
LOAD_BATCH = 20_000

FloatArray = NDArray[np.float64]


def configure_gdal(user_agent: str) -> None:
    os.environ["GDAL_HTTP_USERAGENT"] = user_agent
    os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
    os.environ["GDAL_HTTP_MAX_RETRY"] = "4"
    os.environ["GDAL_HTTP_RETRY_DELAY"] = "2"
    os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif,.TIF,.hdf,.vrt"


@dataclass(frozen=True)
class CellGrid:
    """Maps cell ids to array positions. Row 0 is the northern edge, as in rasters."""

    cell_ids: list[str]
    rows: NDArray[np.int32]
    cols: NDArray[np.int32]
    x_min: int
    y_max: int
    width: int
    height: int

    @property
    def size(self) -> int:
        return len(self.cell_ids)

    def pick(self, array: NDArray[np.floating]) -> FloatArray:
        """Values of a full (height, width) array, one per cell in cell_ids order."""
        return np.asarray(array[self.rows, self.cols], dtype=float)

    def to_array(self, values: FloatArray) -> FloatArray:
        array = np.full((self.height, self.width), np.nan)
        array[self.rows, self.cols] = values
        return array


def grid_from_ids(cell_ids: list[str]) -> CellGrid:
    parsed = [parse_cell_id(value) for value in cell_ids]
    xs = np.array([x for x, _ in parsed], dtype=np.int64)
    ys = np.array([y for _, y in parsed], dtype=np.int64)
    x_min = int(xs.min())
    y_max = int(ys.max()) + CELL_M
    return CellGrid(
        cell_ids=cell_ids,
        rows=((y_max - CELL_M - ys) // CELL_M).astype(np.int32),
        cols=((xs - x_min) // CELL_M).astype(np.int32),
        x_min=x_min,
        y_max=y_max,
        width=int(xs.max() - x_min) // CELL_M + 1,
        height=int(ys.max() - ys.min()) // CELL_M + 1,
    )


def load_grid(conn: Connection) -> CellGrid:
    ids = list(conn.execute(text("SELECT cell_id FROM ref.grid_1km ORDER BY cell_id")).scalars())
    if not ids:
        raise ValueError("ref.grid_1km is empty: run dgu_au first")
    return grid_from_ids(ids)


def cell_centroids_lonlat(grid: CellGrid) -> tuple[FloatArray, FloatArray]:
    x = grid.x_min + (grid.cols.astype(float) + 0.5) * CELL_M
    y = grid.y_max - (grid.rows.astype(float) + 0.5) * CELL_M
    transformer = Transformer.from_crs(3035, 4326, always_xy=True)
    lon, lat = transformer.transform(x, y)
    return np.asarray(lon), np.asarray(lat)


def clip_wgs84(source: str, target: Path, bounds: tuple[float, float, float, float]) -> Path:
    """Copy a window of a remote raster to a compressed local file, once."""
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.part")
    with rasterio.open(source) as dataset:
        west, south, east, north = bounds
        window = (
            from_bounds(west, south, east, north, dataset.transform).round_offsets().round_lengths()
        )
        profile = dataset.profile.copy()
        profile.update(
            driver="GTiff",
            width=window.width,
            height=window.height,
            transform=dataset.window_transform(window),
            compress="deflate",
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )
        with rasterio.open(partial, "w", **profile) as out:
            out.write(dataset.read(1, window=window), 1)
    partial.replace(target)
    return target


def blocks(grid: CellGrid) -> Iterator[tuple[int, int, int, int]]:
    """(row, col, height, width) blocks in cells, so large rasters are read piece by piece."""
    for row in range(0, grid.height, BLOCK_CELLS):
        for col in range(0, grid.width, BLOCK_CELLS):
            yield (
                row,
                col,
                min(BLOCK_CELLS, grid.height - row),
                min(BLOCK_CELLS, grid.width - col),
            )


def warped_to_grid(
    dataset: rasterio.DatasetReader, grid: CellGrid, pixels_per_cell: int
) -> WarpedVRT:
    pixel = CELL_M / pixels_per_cell
    return WarpedVRT(
        dataset,
        crs="EPSG:3035",
        transform=Affine(pixel, 0, grid.x_min, 0, -pixel, grid.y_max),
        width=grid.width * pixels_per_cell,
        height=grid.height * pixels_per_cell,
        resampling=Resampling.nearest,
    )


def reduce_blocks(
    vrt: WarpedVRT,
    grid: CellGrid,
    pixels_per_cell: int,
    reducer: Callable[[NDArray[np.floating]], NDArray[np.floating]],
) -> FloatArray:
    """Apply `reducer` to each (cell_h, cell_w, n, n) block and return a (height, width) array."""
    n = pixels_per_cell
    result = np.full((grid.height, grid.width), np.nan)
    for row, col, height, width in blocks(grid):
        data = vrt.read(1, window=Window(col * n, row * n, width * n, height * n), masked=False)
        shaped = data.reshape(height, n, width, n).transpose(0, 2, 1, 3)
        result[row : row + height, col : col + width] = reducer(shaped)
    return result


def nearest_fill(values: FloatArray, grid: CellGrid, max_cells: int) -> FloatArray:
    """Fill gaps from the nearest cell with a value, within `max_cells` cells."""
    from scipy.ndimage import distance_transform_edt

    array = grid.to_array(values)
    missing = np.isnan(array)
    if not missing.any() or missing.all():
        return values
    distance, indices = distance_transform_edt(missing, return_indices=True)
    filled = array[tuple(indices)]
    filled[distance > max_cells] = np.nan
    return grid.pick(filled)
