import pytest

from klimakompas.core.config import load_crosswalk
from klimakompas.pipeline.population import (
    AgeCounts,
    CensusSettlement,
    DguSettlement,
    age_shares,
    match_settlements,
    normalize_name,
)

COUNTS = AgeCounts(100, 20, 10)
EMPTY_CROSSWALK: dict[str, list[dict[str, str]]] = {
    "jls_renames": [],
    "settlements_without_dgu_match": [],
}


def settlement(zupanija: str, jls: str, naselje: str) -> CensusSettlement:
    return CensusSettlement(zupanija, jls, naselje, COUNTS)


def register(zupanija: str, jls: str, name: str, code: str = "000001") -> DguSettlement:
    return DguSettlement(code, name, "00001", jls, f"{zupanija} županija")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Podstrana – Sita", "Podstrana - Sita"),
        ("Klupci – dio", "Klupci-dio"),
        ("Donja Batina – dio (217 – 258)", "Donja Batina-dio (217-258)"),
        ("Vinišće ", "vinišće"),
    ],
)
def test_normalizes_dash_and_spacing_differences(left: str, right: str) -> None:
    assert normalize_name(left) == normalize_name(right)


def test_matches_bilingual_names_on_the_croatian_part() -> None:
    matches = match_settlements(
        [settlement("Istarska", "Buje – Buie", "Baredine")],
        [register("Istarska", "Buje - Buie", "Baredine - Baredine")],
        EMPTY_CROSSWALK,
    )
    assert matches[0].naselje_code == "000001"


def test_keeps_settlements_with_the_same_prefix_apart() -> None:
    matches = match_settlements(
        [settlement("Splitsko-dalmatinska", "Podstrana", "Podstrana – Sita")],
        [
            register("Splitsko-dalmatinska", "Podstrana", "Podstrana - Grbavac", "076821"),
            register("Splitsko-dalmatinska", "Podstrana", "Podstrana - Sita", "076775"),
        ],
        EMPTY_CROSSWALK,
    )
    assert matches[0].naselje_code == "076775"


def test_renamed_jls_and_listed_settlements_use_the_crosswalk() -> None:
    crosswalk = load_crosswalk("dzs_dgu_naselja")
    matches = match_settlements(
        [
            settlement("Šibensko-kninska", "Murter-Kornati", "Murter"),
            settlement("Zagrebačka", "Vrbovec", "Martinska Ves"),
        ],
        [
            register("Šibensko-kninska", "Murter", "Murter", "042501"),
            register("Zagrebačka", "Vrbovec", "Vrbovec", "000002"),
        ],
        crosswalk,
    )
    assert matches[0].naselje_code == "042501"
    assert matches[1].naselje_code is None
    assert matches[1].jls_code == "00001"


def test_unexplained_census_name_fails_the_load() -> None:
    with pytest.raises(ValueError, match="Nepoznato"):
        match_settlements(
            [settlement("Istarska", "Pula", "Nepoznato")],
            [register("Istarska", "Pula", "Pula")],
            EMPTY_CROSSWALK,
        )


def test_large_cell_uses_its_own_shares() -> None:
    shares = age_shares(50, 10, 5, COUNTS, COUNTS, min_cell_pop=10)
    assert (shares.ge65, shares.lt15, shares.source) == (0.2, 0.1, "cell")


def test_share_is_capped_at_one() -> None:
    assert age_shares(10, 12, 0, COUNTS, COUNTS, min_cell_pop=10).ge65 == 1.0


def test_threshold_is_inclusive() -> None:
    assert age_shares(10, 1, 1, COUNTS, COUNTS, min_cell_pop=10).source == "cell"
    assert age_shares(9, 1, 1, COUNTS, COUNTS, min_cell_pop=10).source == "naselje"


def test_small_cell_prefers_settlement_then_jls() -> None:
    jls = AgeCounts(1000, 300, 100)
    assert age_shares(2, 2, 0, COUNTS, jls, min_cell_pop=10).ge65 == 0.2
    shares = age_shares(2, 2, 0, None, jls, min_cell_pop=10)
    assert (shares.ge65, shares.source) == (0.3, "jls")
    assert age_shares(2, 2, 0, AgeCounts(0, 0, 0), jls, min_cell_pop=10).source == "jls"


def test_confidential_counts_use_the_settlement() -> None:
    assert age_shares(50, None, None, COUNTS, None, min_cell_pop=10).source == "naselje"


def test_empty_cell_has_no_shares() -> None:
    shares = age_shares(0, 0, 0, COUNTS, COUNTS, min_cell_pop=10)
    assert (shares.ge65, shares.lt15, shares.source) == (None, None, None)
