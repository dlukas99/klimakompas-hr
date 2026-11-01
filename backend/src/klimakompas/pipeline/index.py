"""Climate Risk Index (IKR) from hazard layers (SPEC §5.4, §5.5). Pure array functions."""

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from klimakompas.pipeline.hazards import percentile_rank

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int32]

HAZARDS = ("flood", "heat", "fire", "air")


@dataclass(frozen=True)
class CellInputs:
    """Populated cells only, in one shared order."""

    pop_total: IntArray
    share_ge65: FloatArray
    share_lt15: FloatArray
    tree_share: FloatArray
    h: dict[str, FloatArray]
    pm25: FloatArray


@dataclass(frozen=True)
class CellIndex:
    v_gen: FloatArray
    v_heat: FloatArray
    r: dict[str, FloatArray]
    ikr: FloatArray
    ikr_class: IntArray
    classes: dict[str, IntArray]


def config_hash(*texts: str) -> str:
    return hashlib.sha256("\n".join(texts).encode()).hexdigest()


def quintile_classes(values: FloatArray) -> IntArray:
    """Class 1-5 by quintile of the valid values, 0 where the value is missing."""
    result = np.zeros(values.shape, dtype=np.int32)
    valid = ~np.isnan(values)
    if not valid.any():
        return result
    ranks = percentile_rank(values)
    # Equal values share a class, so a large group of zeros never spreads across classes.
    result[valid] = np.minimum(np.floor(ranks[valid] * 5).astype(np.int32) + 1, 5)
    return result


def threshold_classes(values: FloatArray, boundaries: list[float]) -> IntArray:
    """Class 1 up to and including the first boundary, and so on; 0 where the value is missing."""
    result = np.zeros(values.shape, dtype=np.int32)
    valid = ~np.isnan(values)
    result[valid] = np.searchsorted(np.asarray(boundaries), values[valid], side="left") + 1
    return result


def weighted_ikr(r: dict[str, FloatArray], weights: dict[str, float]) -> FloatArray:
    """Weighted mean of the available hazards, so one missing layer does not zero a cell."""
    names = [name for name in r if weights.get(name, 0) > 0]
    stacked = np.stack([r[name] for name in names])
    weight = np.array([weights[name] for name in names])[:, None]
    valid = ~np.isnan(stacked)
    total = (np.where(valid, stacked, 0.0) * weight).sum(axis=0)
    weight_sum = (valid * weight).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        result: FloatArray = np.where(weight_sum > 0, total / weight_sum, np.nan)
    return result


def compute_cell_index(
    inputs: CellInputs, config: dict[str, Any], pm25_levels: list[float]
) -> CellIndex:
    general = config["vulnerability"]["general"]
    heat = config["vulnerability"]["heat"]
    base = float(config["risk"]["base"])

    v_gen = general["share_65plus"] * percentile_rank(inputs.share_ge65) + general[
        "share_under15"
    ] * percentile_rank(inputs.share_lt15)
    v_heat = heat["general"] * v_gen + heat["tree_deficit"] * (1 - inputs.tree_share)

    vulnerability = {"flood": v_gen, "heat": v_heat, "fire": v_gen, "air": v_gen}
    r = {name: inputs.h[name] * (base + (1 - base) * vulnerability[name]) for name in HAZARDS}
    ikr = weighted_ikr(r, config["ikr"]["weights"])

    classes = {
        "flood": threshold_classes(
            inputs.h["flood"], config["hazards"]["flood"]["cell_class_breaks"]
        ),
        "heat": quintile_classes(r["heat"]),
        "fire": quintile_classes(r["fire"]),
        "air": threshold_classes(inputs.pm25, pm25_levels),
    }
    return CellIndex(v_gen, v_heat, r, ikr, quintile_classes(ikr), classes)


@dataclass(frozen=True)
class Aggregate:
    pop: float
    pop65: float
    ikr_popw: float | None
    exposed: dict[str, dict[str, float]]


def aggregate_cells(
    pop: FloatArray,
    share_ge65: FloatArray,
    ikr: FloatArray,
    classes: dict[str, IntArray],
    high_class_min: int,
) -> Aggregate:
    """Population-weighted IKR and people in cells of a high class, for one area."""
    pop65 = pop * np.nan_to_num(share_ge65)
    valid = ~np.isnan(ikr)
    weight = pop[valid].sum()
    ikr_popw = float((pop[valid] * ikr[valid]).sum() / weight) if weight > 0 else None
    total = float(pop.sum())
    exposed = {}
    for name, values in classes.items():
        high = values >= high_class_min
        people = float(pop[high].sum())
        exposed[name] = {
            "pop": people,
            "pop65": float(pop65[high].sum()),
            "share": people / total if total > 0 else 0.0,
        }
    return Aggregate(total, float(pop65.sum()), ikr_popw, exposed)


def competition_ranks(values: FloatArray) -> IntArray:
    """Rank 1 is the highest value; ties share a rank, and missing values get 0."""
    from scipy.stats import rankdata

    result = np.zeros(values.shape, dtype=np.int32)
    valid = ~np.isnan(values)
    if valid.any():
        result[valid] = rankdata(-values[valid], method="min").astype(np.int32)
    return result
