"""WorldCover, Landsat LST and MODIS burnt area on the 1 km grid, read through STAC.

Pixels are accumulated into cells from COG overviews, so nothing large is loaded at once. Progress
is kept in data/interim, so an interrupted run continues where it stopped.
"""

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import numpy as np
import rasterio
import structlog
from numpy.typing import NDArray
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.windows import Window
from scipy.ndimage import binary_dilation, uniform_filter
from scipy.spatial import cKDTree

from klimakompas.core.http import HttpClient
from klimakompas.pipeline.raster import BOUNDS_WGS84, CELL_M, CellGrid

log = structlog.get_logger()

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
TOKEN_MAX_AGE_S = 600
ROW_CHUNK = 512
PAGE_SIZE = 200

WORLDCOVER_DECIMATION = 8
LANDSAT_DECIMATION = 4
# QA_PIXEL bits: dilated cloud, cloud, cloud shadow, snow (SPEC §4.2).
LANDSAT_QA_MASK = (1 << 1) | (1 << 3) | (1 << 4) | (1 << 5)
LANDSAT_MIN_CELL_PIXELS = 15
KELVIN = 273.15


class Signer:
    """Appends a Planetary Computer SAS token. Tokens are per storage container and short-lived."""

    def __init__(self, client: HttpClient) -> None:
        self.client = client
        self.tokens: dict[str, tuple[str, float]] = {}

    def sign(self, href: str) -> str:
        parts = urlsplit(href)
        account = parts.netloc.split(".")[0]
        container = parts.path.strip("/").split("/")[0]
        key = f"{account}/{container}"
        token, fetched = self.tokens.get(key, ("", -TOKEN_MAX_AGE_S))
        if time.monotonic() - fetched > TOKEN_MAX_AGE_S:
            response = self.client.request("GET", f"{SAS}/{key}")
            response.raise_for_status()
            token = response.json()["token"]
            self.tokens[key] = (token, time.monotonic())
        return f"/vsicurl/{href}?{token}"


def search_items(client: HttpClient, body: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """All STAC items for a search, following the paging links."""
    payload: dict[str, Any] = {"bbox": list(BOUNDS_WGS84), "limit": PAGE_SIZE, **body}
    while True:
        response = client.request("POST", f"{STAC}/search", json=payload)
        response.raise_for_status()
        page = response.json()
        yield from page["features"]
        following = [link for link in page.get("links", []) if link.get("rel") == "next"]
        if not following:
            return
        payload = following[0]["body"]


def _pixel_cells(
    dataset: rasterio.DatasetReader, window: Window, shape: tuple[int, int], grid: CellGrid
) -> NDArray[np.int64]:
    """Flat cell index for each output pixel centre, -1 when outside the grid."""
    transform = dataset.window_transform(window) * rasterio.Affine.scale(
        window.width / shape[1], window.height / shape[0]
    )
    cols, rows = np.meshgrid(np.arange(shape[1]) + 0.5, np.arange(shape[0]) + 0.5)
    xs, ys = transform * (cols, rows)
    east, north = Transformer.from_crs(dataset.crs, 3035, always_xy=True).transform(xs, ys)
    cell_col = np.floor((np.asarray(east) - grid.x_min) / CELL_M).astype(np.int64)
    cell_row = np.floor((grid.y_max - np.asarray(north)) / CELL_M).astype(np.int64)
    inside = (cell_col >= 0) & (cell_col < grid.width) & (cell_row >= 0) & (cell_row < grid.height)
    flat = cell_row * grid.width + cell_col
    flat[~inside] = -1
    return flat


def _read_chunks(
    dataset: rasterio.DatasetReader, decimation: int
) -> Iterator[tuple[Window, tuple[int, int], NDArray[Any]]]:
    width = dataset.width // decimation
    for start in range(0, dataset.height // decimation, ROW_CHUNK):
        rows = min(ROW_CHUNK, dataset.height // decimation - start)
        window = Window(0, start * decimation, dataset.width, rows * decimation)
        data = dataset.read(
            1, window=window, out_shape=(rows, width), resampling=Resampling.nearest
        )
        yield window, (rows, width), data


def _bincount(cells: NDArray[np.int64], size: int, weights: NDArray[Any] | None = None) -> Any:
    return np.bincount(cells, weights=weights, minlength=size)


def worldcover_counts(client: HttpClient, grid: CellGrid, cache: Path) -> dict[int, NDArray[Any]]:
    """Pixel counts per land cover class and cell, as (height, width) arrays."""
    if cache.exists():
        with np.load(cache) as stored:
            return {int(name): stored[name] for name in stored.files}
    classes = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100)
    lookup = np.zeros(256, dtype=np.int64)
    for position, value in enumerate(classes):
        lookup[value] = position
    size = grid.width * grid.height
    totals = np.zeros((len(classes), size), dtype=np.int64)
    signer = Signer(client)
    items = list(
        search_items(
            client,
            {
                "collections": ["esa-worldcover"],
                "query": {"esa_worldcover:product_version": {"eq": "2.0.0"}},
            },
        )
    )
    log.info("worldcover tiles", count=len(items))
    for item in items:
        with rasterio.open(signer.sign(item["assets"]["map"]["href"])) as dataset:
            for window, shape, data in _read_chunks(dataset, WORLDCOVER_DECIMATION):
                cells = _pixel_cells(dataset, window, shape, grid)
                keep = cells >= 0
                if keep.any():
                    pairs = lookup[data[keep]] * size + cells[keep]
                    counted = np.bincount(pairs, minlength=len(classes) * size)
                    totals += counted.reshape(len(classes), size)
        log.info("worldcover tile done", item=item["id"])
    result = {
        value: totals[position].reshape(grid.height, grid.width).astype(np.int32)
        for position, value in enumerate(classes)
        if value != 0
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **{str(key): array for key, array in result.items()})
    return result


def landcover_shares(
    counts: dict[int, NDArray[Any]], grid: CellGrid, fuel_classes: list[int]
) -> dict[str, NDArray[np.float64]]:
    """Shares per cell. Tree, built-up and fuel shares are of land, so sea does not dilute them."""
    total = sum(array.astype(float) for array in counts.values())
    assert isinstance(total, np.ndarray)
    water = counts[80].astype(float)
    land = total - water
    fuel_counts = sum(counts[value].astype(float) for value in fuel_classes)
    assert isinstance(fuel_counts, np.ndarray)

    def share(part: NDArray[Any], whole: NDArray[Any]) -> NDArray[np.float64]:
        result: NDArray[np.float64] = np.divide(
            part, whole, out=np.zeros_like(whole, dtype=float), where=whole > 0
        )
        return result

    # The cell plus a 1 km ring is its 3 x 3 neighbourhood.
    ring_fuel = uniform_filter(fuel_counts, size=3, mode="constant")
    ring_land = uniform_filter(land, size=3, mode="constant")
    return {
        "tree_share": grid.pick(np.clip(share(counts[10].astype(float), land), 0, 1)),
        "builtup_share": grid.pick(np.clip(share(counts[50].astype(float), land), 0, 1)),
        "water_share": grid.pick(np.clip(share(water, total), 0, 1)),
        "fuel_share": grid.pick(np.clip(share(ring_fuel, ring_land), 0, 1)),
    }


def _landsat_scene(
    href_lwir: str, href_qa: str, scale: float, offset: float, grid: CellGrid
) -> NDArray[np.float32]:
    """Mean surface temperature per cell in °C for one scene, NaN where too few clear pixels."""
    size = grid.width * grid.height
    total = np.zeros(size)
    count = np.zeros(size)
    with rasterio.open(href_lwir) as lwir, rasterio.open(href_qa) as qa:
        for (window, shape, data), (_, _, flags) in zip(
            _read_chunks(lwir, LANDSAT_DECIMATION),
            _read_chunks(qa, LANDSAT_DECIMATION),
            strict=True,
        ):
            clear = (data > 0) & ((flags & LANDSAT_QA_MASK) == 0)
            if not clear.any():
                continue
            cells = _pixel_cells(lwir, window, shape, grid)
            keep = clear & (cells >= 0)
            if keep.any():
                celsius = data[keep].astype(float) * scale + offset - KELVIN
                total += _bincount(cells[keep], size, celsius)
                count += _bincount(cells[keep], size)
    mean = np.full(size, np.nan, dtype=np.float32)
    enough = count >= LANDSAT_MIN_CELL_PIXELS
    mean[enough] = (total[enough] / count[enough]).astype(np.float32)
    flat = grid.rows.astype(np.int64) * grid.width + grid.cols
    result: NDArray[np.float32] = mean[flat]
    return result


def landsat_median(
    client: HttpClient, grid: CellGrid, config: dict[str, Any], folder: Path
) -> NDArray[np.float64]:
    """Median across scenes of the per-cell mean, per scene. Finished scenes are kept on disk."""
    folder.mkdir(parents=True, exist_ok=True)
    signer = Signer(client)
    items: list[dict[str, Any]] = []
    for year in config["years"]:
        months = config["months"]
        start = f"{year}-{min(months):02d}-01T00:00:00Z"
        end = f"{year}-{max(months):02d}-31T23:59:59Z"
        items.extend(
            search_items(
                client,
                {
                    "collections": ["landsat-c2-l2"],
                    "datetime": f"{start}/{end}",
                    "query": {
                        "eo:cloud_cover": {"lt": config["max_cloud"]},
                        "platform": {"in": ["landsat-8", "landsat-9"]},
                    },
                },
            )
        )
    log.info("landsat scenes", count=len(items))
    for position, item in enumerate(items):
        target = folder / f"{item['id']}.npy"
        if target.exists():
            continue
        lwir = item["assets"]["lwir11"]
        band = lwir["raster:bands"][0]
        try:
            scene = _landsat_scene(
                signer.sign(lwir["href"]),
                signer.sign(item["assets"]["qa_pixel"]["href"]),
                float(band["scale"]),
                float(band["offset"]),
                grid,
            )
        except rasterio.errors.RasterioIOError as error:
            log.warning("landsat scene skipped", item=item["id"], error=str(error)[:200])
            continue
        partial = target.with_name(f"{target.stem}.part.npy")
        np.save(partial, scene)
        partial.replace(target)
        if position % 10 == 0:
            log.info("landsat progress", done=position + 1, total=len(items))
    stack = np.stack([np.load(path) for path in sorted(folder.glob("LC*.npy"))])
    log.info("landsat stack", shape=stack.shape)
    with np.errstate(all="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            result: NDArray[np.float64] = np.nanmedian(stack, axis=0).astype(float)
    return result


def lst_delta(
    lst: NDArray[np.float64],
    builtup: NDArray[np.float64],
    water: NDArray[np.float64],
    grid: CellGrid,
    rural_builtup_max: float,
    radius_km: float,
) -> NDArray[np.float64]:
    """Cell LST minus the median LST of rural cells within the radius (SPEC §5.3b)."""
    x = grid.cols.astype(float) * CELL_M
    y = grid.rows.astype(float) * CELL_M
    points = np.column_stack((x, y))
    rural = (builtup < rural_builtup_max) & (water < 0.5) & ~np.isnan(lst)
    rural_lst = lst[rural]
    tree = cKDTree(points[rural])
    neighbours = tree.query_ball_point(points, r=radius_km * 1000, workers=-1)
    delta = np.full_like(lst, np.nan)
    for index, near in enumerate(neighbours):
        if near and not np.isnan(lst[index]):
            delta[index] = lst[index] - np.median(rural_lst[near])
    return delta


def burnt_years(
    client: HttpClient, grid: CellGrid, config: dict[str, Any], folder: Path
) -> NDArray[np.float64]:
    """Number of years with burnt area within the buffer of each cell."""
    folder.mkdir(parents=True, exist_ok=True)
    signer = Signer(client)
    first, last = config["years"]
    radius = int(config["buffer_km"])
    y, x = np.ogrid[-radius : radius + 1, -radius : radius + 1]
    disk = x * x + y * y <= radius * radius
    size = grid.width * grid.height
    years = np.zeros((grid.height, grid.width), dtype=np.int32)
    for year in range(first, last + 1):
        target = folder / f"burnt_{year}.npy"
        if not target.exists():
            burnt = np.zeros(size, dtype=bool)
            items = search_items(
                client,
                {
                    "collections": ["modis-64A1-061"],
                    "datetime": f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z",
                },
            )
            for item in items:
                with rasterio.open(signer.sign(item["assets"]["Burn_Date"]["href"])) as dataset:
                    window = Window(0, 0, dataset.width, dataset.height)
                    data = dataset.read(1)
                    if not (data > 0).any():
                        continue
                    cells = _pixel_cells(dataset, window, data.shape, grid)
                    hits = cells[(data > 0) & (cells >= 0)]
                    burnt[hits] = True
            np.save(target, burnt)
            log.info("burnt year done", year=year, cells=int(burnt.sum()))
        burnt_year = np.load(target).reshape(grid.height, grid.width)
        years += binary_dilation(burnt_year, structure=disk)
    return grid.pick(years.astype(float))
