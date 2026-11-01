"""Golden tests for the formulas in SPEC §5.3-5.5, with values worked out by hand."""

import numpy as np
import pytest

from klimakompas.core.config import load_index_config, load_thresholds
from klimakompas.pipeline.hazards import (
    air_card_level,
    air_hazard,
    fire_hazard,
    flood_card_level,
    flood_eaf,
    flood_hazard,
    heat_hazard,
    percentile_rank,
    robust_minmax,
    station_corrected,
)
from klimakompas.pipeline.index import (
    CellInputs,
    aggregate_cells,
    competition_ranks,
    compute_cell_index,
    quintile_classes,
    threshold_classes,
    weighted_ikr,
)


def arr(*values: float) -> np.ndarray:
    return np.array(values, dtype=float)


@pytest.mark.parametrize(
    ("s10", "s100", "s500", "expected"),
    [(1, 1, 1, 1.0), (0, 1, 1, 0.55), (0, 0, 1, 0.06), (0, 0, 0, 0.0)],
)
def test_flood_hazard_matches_spec_examples(
    s10: float, s100: float, s500: float, expected: float
) -> None:
    eaf = flood_eaf(arr(s10), arr(s100), arr(s500))
    assert flood_hazard(eaf, 0.10)[0] == pytest.approx(expected)


def test_flood_applies_monotonicity() -> None:
    # RP10 flooded but RP100 and RP500 not: the longer return periods must cover at least as much.
    assert flood_eaf(arr(1), arr(0), arr(0))[0] == pytest.approx(0.10)


def test_flood_hazard_is_capped_at_one() -> None:
    assert flood_hazard(arr(0.5), 0.10)[0] == 1.0


@pytest.mark.parametrize(
    ("depths", "near", "level"),
    [
        ((1.0, 2.0, 3.0), False, 5),
        ((0.0, 2.0, 3.0), False, 4),
        ((None, None, 0.1), False, 3),
        ((0.0, 0.0, 0.0), True, 2),
        ((None, None, None), False, 1),
    ],
)
def test_flood_card_levels(
    depths: tuple[float | None, float | None, float | None], near: bool, level: int
) -> None:
    levels = load_index_config()["hazards"]["flood"]["card_levels"]
    assert flood_card_level(*depths, near, levels) == level


def test_air_hazard_bounds() -> None:
    assert air_hazard(arr(3, 5, 15, 25, 40), 5, 25).tolist() == [0, 0, 0.5, 1, 1]


@pytest.mark.parametrize(
    ("value", "level"), [(5, 1), (5.1, 2), (10, 2), (15, 3), (25, 4), (25.1, 5)]
)
def test_air_card_levels(value: float, level: int) -> None:
    assert air_card_level(value, load_thresholds()["pm25_annual_ugm3"]["card_levels"]) == level


def test_robust_minmax_uses_reference_percentiles() -> None:
    reference = np.arange(0.0, 101.0)
    result = robust_minmax(arr(0, 5, 50, 95, 100), reference, 5, 95)
    assert result.tolist() == [0, 0, pytest.approx(0.5), 1, 1]


def test_robust_minmax_with_constant_reference_is_zero() -> None:
    assert robust_minmax(arr(1, 2), arr(3, 3, 3), 5, 95).tolist() == [0, 0]


def test_percentile_rank_is_0_to_1_and_keeps_nan() -> None:
    result = percentile_rank(arr(10, np.nan, 30, 20))
    assert result[0] == 0
    assert np.isnan(result[1])
    assert result[2] == 1
    assert result[3] == 0.5


def test_heat_hazard_weights() -> None:
    weights = {"hot_days": 0.5, "tropical_nights": 0.25, "lst_delta": 0.25}
    assert heat_hazard(arr(1), arr(0), arr(0), weights)[0] == 0.5
    assert heat_hazard(arr(0), arr(0), arr(1), weights)[0] == 0.25


def test_heat_hazard_without_lst_reweights() -> None:
    weights = {"hot_days": 0.5, "tropical_nights": 0.25, "lst_delta": 0.25}
    assert heat_hazard(arr(1), arr(0), None, weights)[0] == pytest.approx(2 / 3)
    # One cell without a valid scene is reweighted the same way.
    assert heat_hazard(arr(1), arr(0), arr(np.nan), weights)[0] == pytest.approx(2 / 3)


def test_fire_hazard_formula() -> None:
    # 0.7 * 1 * (0.3 + 0.7 * 0.5) + 0.3 * 0.5
    result = fire_hazard(arr(1), arr(0.5), arr(0.5), 0.7, 0.3, 0.3)
    assert result[0] == pytest.approx(0.605)


def test_fire_hazard_keeps_floor_without_fuel() -> None:
    assert fire_hazard(arr(1), arr(0), arr(0), 0.7, 0.3, 0.3)[0] == pytest.approx(0.21)


def test_weighted_ikr_skips_missing_hazard() -> None:
    r = {"flood": arr(1, 1), "air": arr(0, np.nan)}
    assert weighted_ikr(r, {"flood": 0.25, "air": 0.25}).tolist() == [0.5, 1.0]


def test_weighted_ikr_all_missing_is_nan() -> None:
    assert np.isnan(weighted_ikr({"flood": arr(np.nan)}, {"flood": 0.25})[0])


def test_quintiles_split_evenly_and_keep_ties_together() -> None:
    classes = quintile_classes(np.arange(10.0))
    assert classes.tolist() == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert len(set(quintile_classes(arr(2, 2, 2, 2)).tolist())) == 1


def test_threshold_classes() -> None:
    breaks = load_index_config()["hazards"]["flood"]["cell_class_breaks"]
    values = arr(0, 0.02, 0.06, 0.55, 1.0, np.nan)
    assert threshold_classes(values, breaks).tolist() == [1, 2, 3, 4, 5, 0]


def test_risk_formula_end_to_end() -> None:
    config = load_index_config()
    inputs = CellInputs(
        pop_total=np.array([100, 200], dtype=np.int32),
        share_ge65=arr(0.1, 0.3),
        share_lt15=arr(0.2, 0.1),
        tree_share=arr(0.5, 0.0),
        h={"flood": arr(1, 0), "heat": arr(0, 1), "fire": arr(0, 0), "air": arr(0, 0.5)},
        pm25=arr(4, 15),
    )
    result = compute_cell_index(inputs, config, [5, 10, 15, 25])
    # Cell 1 has the lowest 65+ rank and the highest under-15 rank: V_gen = 0.7*0 + 0.3*1.
    assert result.v_gen[0] == pytest.approx(0.3)
    assert result.v_gen[1] == pytest.approx(0.7)
    assert result.r["flood"][0] == pytest.approx(1 * (0.5 + 0.5 * 0.3))
    # V_heat of cell 2 = 0.6*0.7 + 0.4*(1-0).
    assert result.v_heat[1] == pytest.approx(0.82)
    assert result.r["heat"][1] == pytest.approx(0.5 + 0.5 * 0.82)
    assert result.ikr[0] == pytest.approx(0.65 / 4)
    assert result.classes["air"].tolist() == [1, 3]


def test_aggregation_weights_by_population_and_counts_exposed_people() -> None:
    result = aggregate_cells(
        arr(100, 300),
        arr(0.5, 0.1),
        arr(0.2, 0.6),
        {"flood": np.array([5, 1], dtype=np.int32)},
        high_class_min=4,
    )
    assert result.pop == 400
    assert result.pop65 == pytest.approx(80)
    assert result.ikr_popw == pytest.approx(0.5)
    assert result.exposed["flood"] == {"pop": 100, "pop65": 50, "share": 0.25}


def test_ranks_highest_first_with_ties_and_missing() -> None:
    assert competition_ranks(arr(0.5, 0.9, 0.5, np.nan)).tolist() == [2, 1, 2, 0]


def test_station_correction_applies_residual_near_a_station_only() -> None:
    corrected, _, raw_mae = station_corrected(
        arr(2, 2),
        target_x=arr(0, 500_000),
        target_y=arr(0, 0),
        x=arr(0),
        y=arr(0),
        grid_at_stations=arr(2),
        observed=arr(44),
        neighbours=5,
        max_m=100_000,
    )
    assert corrected.tolist() == [44, 2]
    assert raw_mae == 42


def test_station_correction_reports_leave_one_out_error() -> None:
    # Both stations have the same residual of +10, so each one predicts the other exactly.
    _, loo_mae, raw_mae = station_corrected(
        arr(0),
        target_x=arr(0),
        target_y=arr(0),
        x=arr(0, 1000),
        y=arr(0, 0),
        grid_at_stations=arr(5, 5),
        observed=arr(15, 15),
        neighbours=5,
        max_m=100_000,
    )
    assert loo_mae == 0
    assert raw_mae == 10


def test_station_correction_never_goes_below_zero() -> None:
    corrected, _, _ = station_corrected(
        arr(1), arr(0), arr(0), arr(0), arr(0), arr(20), arr(0), 5, 100_000
    )
    assert corrected[0] == 0
