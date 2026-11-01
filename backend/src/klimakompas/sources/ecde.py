"""ECDE climate indicators from the Copernicus CDS (values taken from the process constraints)."""

import zipfile
from pathlib import Path

import cdsapi
import numpy as np
import xarray as xr
from scipy.spatial import cKDTree
from sqlalchemy import Connection

from klimakompas.core.config import Settings
from klimakompas.pipeline.raster import CellGrid, cell_centroids_lonlat

DATASET = "sis-ecde-climate-indicators"
VERSION = "v2_0"
REQUESTS: dict[str, dict[str, str | list[str]]] = {
    "hot_days": {"variable": ["hot_days"], "other_parameters": ["30_c"]},
    "tropical_nights": {"variable": ["tropical_nights"]},
    "fwi_days": {"variable": ["days_with_high_fire_danger"]},
}


def fetch_indicator(settings: Settings, name: str, folder: Path) -> Path:
    """Request one indicator. CDS requests wait in a queue, so this can take a long time."""
    target = folder / f"{name}.zip"
    if target.exists():
        return target
    folder.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client(
        url=settings.cdsapi_url, key=settings.cdsapi_key.get_secret_value(), quiet=True
    )
    partial = folder / f"{name}.zip.part"
    client.retrieve(
        DATASET,
        {
            "origin": "reanalysis",
            "temporal_aggregation": ["yearly"],
            "spatial_aggregation": "gridded",
            "version": VERSION,
            **REQUESTS[name],
        },
        str(partial),
    )
    partial.replace(target)
    return target


def extract_netcdf(archive_path: Path, folder: Path) -> list[Path]:
    """Unpack the NetCDF members of a CDS archive; the download may also be plain NetCDF."""
    if not zipfile.is_zipfile(archive_path):
        return [archive_path]
    with zipfile.ZipFile(archive_path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".nc")]
        archive.extractall(folder, members=names)
    return [folder / name for name in names]


def _data_variable(dataset: xr.Dataset) -> xr.DataArray:
    names = [
        name for name, variable in dataset.data_vars.items() if {"lat", "lon"} <= set(variable.dims)
    ]
    if len(names) != 1:
        raise ValueError(f"expected one gridded variable, found {names}")
    return dataset[names[0]]


def climatology(
    paths: list[Path], first_year: int, last_year: int, bounds: tuple[float, float, float, float]
) -> xr.DataArray:
    """Mean annual value over the reference period, cut to `bounds` (west, south, east, north)."""
    if len(paths) != 1:
        raise ValueError(f"expected one NetCDF file, found {len(paths)}")
    with xr.open_dataset(paths[0]) as dataset:
        data = _data_variable(dataset)
        west, south, east, north = bounds
        data = data.sel(lon=slice(west, east))
        ascending = bool(data["lat"][0] < data["lat"][-1])
        data = data.sel(lat=slice(south, north) if ascending else slice(north, south))
        years = data["time"].dt.year
        data = data.where((years >= first_year) & (years <= last_year), drop=True)
        return data.mean("time", skipna=True).load()


def interpolate_points(field: xr.DataArray, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    return np.asarray(
        field.interp(
            lon=xr.DataArray(lon, dims="point"),
            lat=xr.DataArray(lat, dims="point"),
            method="linear",
        ).to_numpy(),
        dtype=float,
    )


def interpolate_to_cells(field: xr.DataArray, conn: Connection, grid: CellGrid) -> np.ndarray:
    """Bilinear interpolation to cell centroids, then nearest for coastal cells left empty."""
    lon, lat = cell_centroids_lonlat(grid)
    points = field.interp(
        lon=xr.DataArray(lon, dims="cell"), lat=xr.DataArray(lat, dims="cell"), method="linear"
    ).to_numpy()
    missing = np.isnan(points)
    if missing.any():
        # Coastal cells can fall outside the land mask of the climate grid.
        lat_grid, lon_grid = np.meshgrid(
            field["lat"].to_numpy(), field["lon"].to_numpy(), indexing="ij"
        )
        values = field.transpose("lat", "lon").to_numpy()
        valid = ~np.isnan(values)
        tree = cKDTree(np.column_stack((lon_grid[valid], lat_grid[valid])))
        _, nearest = tree.query(np.column_stack((lon[missing], lat[missing])))
        points[missing] = values[valid][nearest]
    return np.asarray(points, dtype=float)
