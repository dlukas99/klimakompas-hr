"""Pure hazard formulas (SPEC §5.3). All parameters come from config/index.yaml."""

from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def clamp01(values: FloatArray) -> FloatArray:
    return np.clip(values, 0.0, 1.0)


def robust_minmax(values: FloatArray, reference: FloatArray, low: float, high: float) -> FloatArray:
    """rn(x) with percentiles taken over `reference` (the populated cells)."""
    lower, upper = np.nanpercentile(reference, [low, high])
    if upper <= lower:
        return np.zeros_like(values)
    return clamp01((values - lower) / (upper - lower))


def percentile_rank(values: FloatArray) -> FloatArray:
    """pr(x) in 0-1; ties share their average rank and NaN stays NaN."""
    from scipy.stats import rankdata

    result = np.full_like(values, np.nan, dtype=float)
    valid = ~np.isnan(values)
    count = int(valid.sum())
    if count == 0:
        return result
    if count == 1:
        result[valid] = 0.5
        return result
    result[valid] = (rankdata(values[valid], method="average") - 1) / (count - 1)
    return result


def flood_monotonic(
    s10: FloatArray, s100: FloatArray, s500: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray]:
    s100_m = np.maximum(s100, s10)
    return s10, s100_m, np.maximum(s500, s100_m)


def flood_eaf(s10: FloatArray, s100: FloatArray, s500: FloatArray) -> FloatArray:
    """Expected annual flooded share, trapezoid over annual probabilities 1/RP."""
    a, b, c = flood_monotonic(s10, s100, s500)
    return (0.10 - 0.01) * (a + b) / 2 + (0.01 - 0.002) * (b + c) / 2 + 0.002 * c


def flood_hazard(eaf: FloatArray, eaf_ref: float) -> FloatArray:
    return np.minimum(1.0, eaf / eaf_ref)


def flood_card_level(
    depth_rp10: float | None,
    depth_rp100: float | None,
    depth_rp500: float | None,
    near_rp100: bool,
    levels: dict[str, Any],
) -> int:
    """Card level at a point. Missing raster values count as no flooding there."""
    if (depth_rp10 or 0) > 0:
        return int(levels["rp10"])
    if (depth_rp100 or 0) > 0:
        return int(levels["rp100"])
    if (depth_rp500 or 0) > 0:
        return int(levels["rp500"])
    return int(levels["near_level"] if near_rp100 else levels["else"])


def air_hazard(pm25: FloatArray, zero_at: float, one_at: float) -> FloatArray:
    return clamp01((pm25 - zero_at) / (one_at - zero_at))


def air_card_level(pm25: float, boundaries: list[float]) -> int:
    """Level 1-5: the first boundary the value does not exceed."""
    for level, boundary in enumerate(boundaries, start=1):
        if pm25 <= boundary:
            return level
    return len(boundaries) + 1


def heat_hazard(
    hot_days_rn: FloatArray,
    tropical_rn: FloatArray,
    lst_rn: FloatArray | None,
    weights: dict[str, float],
) -> FloatArray:
    """Without LST, its weight moves to the other two in proportion (0.67 / 0.33)."""
    hot = weights["hot_days"]
    tropical = weights["tropical_nights"]
    lst = weights["lst_delta"]
    if lst_rn is None:
        return (hot * hot_days_rn + tropical * tropical_rn) / (hot + tropical)
    # Cells with no valid LST scenes keep the climate terms, reweighted the same way.
    no_lst = (hot * hot_days_rn + tropical * tropical_rn) / (hot + tropical)
    with_lst = hot * hot_days_rn + tropical * tropical_rn + lst * lst_rn
    return np.where(np.isnan(lst_rn), no_lst, with_lst)


def fire_hazard(
    fwi_rn: FloatArray,
    fuel_share: FloatArray,
    burnt_rn: FloatArray,
    fwi_weight: float,
    burnt_weight: float,
    fuel_floor: float,
) -> FloatArray:
    return fwi_weight * fwi_rn * (fuel_floor + (1 - fuel_floor) * fuel_share) + (
        burnt_weight * burnt_rn
    )


def idw_correction(
    target_x: FloatArray,
    target_y: FloatArray,
    x: FloatArray,
    y: FloatArray,
    residuals: FloatArray,
    neighbours: int,
    max_m: float,
) -> FloatArray:
    """Inverse-distance-squared mean of the nearest station residuals; 0 beyond `max_m`."""
    from scipy.spatial import cKDTree

    count = min(neighbours, len(residuals))
    distance, index = cKDTree(np.column_stack((x, y))).query(
        np.column_stack((target_x, target_y)), k=count
    )
    distance = distance.reshape(len(target_x), count)
    index = index.reshape(len(target_x), count)
    weight = 1.0 / np.maximum(distance, 1.0) ** 2
    weight[distance > max_m] = 0.0
    total = weight.sum(axis=1)
    values = (weight * residuals[index]).sum(axis=1)
    result: FloatArray = np.divide(values, total, out=np.zeros_like(values), where=total > 0)
    return result


def station_corrected(
    grid_values: FloatArray,
    target_x: FloatArray,
    target_y: FloatArray,
    x: FloatArray,
    y: FloatArray,
    grid_at_stations: FloatArray,
    observed: FloatArray,
    neighbours: int,
    max_m: float,
) -> tuple[FloatArray, float, float]:
    """Grid field plus interpolated station residuals, never below zero.

    Also returns the leave-one-out mean absolute error, before and after the correction.
    """
    residuals = observed - grid_at_stations
    corrected = np.maximum(
        grid_values + idw_correction(target_x, target_y, x, y, residuals, neighbours, max_m), 0.0
    )
    errors = []
    for i in range(len(observed) if len(observed) > 1 else 0):
        keep = np.arange(len(observed)) != i
        residual = idw_correction(
            x[[i]], y[[i]], x[keep], y[keep], residuals[keep], neighbours, max_m
        )[0]
        errors.append(abs(max(grid_at_stations[i] + residual, 0.0) - observed[i]))
    loo_mae = float(np.mean(errors)) if errors else float("nan")
    return corrected, loo_mae, float(np.mean(np.abs(residuals)))
