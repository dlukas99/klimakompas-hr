"""Sensitivity of the JLS ranking to the hazard weights (SPEC §5.6)."""

import json
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.stats import spearmanr
from sqlalchemy import Connection, text

from klimakompas.core.config import ROOT, load_index_config

RESULTS_PATH = ROOT / "docs" / "osjetljivost-rezultati.json"
SEED = 2026
STABLE_SHARE = 0.8
HAZARDS = ("flood", "heat", "fire", "air")


def sensitivity(
    risks: NDArray[np.float64],
    base_weights: NDArray[np.float64],
    samples: int,
    alpha: float,
    top_n: int,
    seed: int = SEED,
) -> dict[str, Any]:
    """`risks` has one row per area and one column per hazard. NaN counts as no risk."""
    filled = np.nan_to_num(risks)
    base = filled @ (base_weights / base_weights.sum())
    base_top = set(np.argsort(-base)[:top_n])
    generator = np.random.default_rng(seed)
    weights = generator.dirichlet(np.full(risks.shape[1], alpha), size=samples)
    scores = filled @ weights.T
    correlations = np.empty(samples)
    in_top = np.zeros(risks.shape[0])
    for index in range(samples):
        column = scores[:, index]
        correlations[index] = spearmanr(base, column).statistic
        in_top[np.argsort(-column)[:top_n]] += 1
    share = in_top / samples
    stable = [int(item) for item in base_top if share[item] >= STABLE_SHARE]
    return {
        "samples": samples,
        "median_spearman": float(np.nanmedian(correlations)),
        "p05_spearman": float(np.nanpercentile(correlations, 5)),
        "top_n": top_n,
        "stable_in_top": len(stable),
        "stable_share_of_top": len(stable) / top_n,
        "stable_indices": sorted(stable),
    }


def run_sensitivity(conn: Connection) -> dict[str, Any]:
    config = load_index_config()
    rows = conn.execute(
        text(
            """
            SELECT j.name,
                   sum(r.pop_total * r.r_flood) / nullif(sum(r.pop_total), 0) AS flood,
                   sum(r.pop_total * r.r_heat) / nullif(sum(r.pop_total), 0) AS heat,
                   sum(r.pop_total * r.r_fire) / nullif(sum(r.pop_total), 0) AS fire,
                   sum(r.pop_total * r.r_air) / nullif(sum(r.pop_total), 0) AS air
            FROM idx.current_risk_cell r
            JOIN ref.grid_1km c USING (cell_id)
            JOIN ref.jls j ON j.code = c.jls_code
            GROUP BY j.code, j.name
            ORDER BY j.code
            """
        )
    ).all()
    risks = np.array([[getattr(row, name) for name in HAZARDS] for row in rows], dtype=float)
    weights = np.array([config["ikr"]["weights"][name] for name in HAZARDS], dtype=float)
    settings = config["sensitivity"]
    result = sensitivity(
        risks,
        weights,
        int(settings["samples"]),
        float(settings["dirichlet_alpha"]),
        int(settings["top_n"]),
    )
    result["stable_names"] = [rows[index].name for index in result.pop("stable_indices")]
    RESULTS_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
