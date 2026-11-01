"""Pure population logic: census-to-register name matching and cell age shares (ADR 0005)."""

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

AgeShareSource = Literal["cell", "naselje", "jls"]


@dataclass(frozen=True)
class AgeCounts:
    total: int
    ge65: int
    lt15: int


@dataclass(frozen=True)
class DguSettlement:
    code: str
    name: str
    jls_code: str
    jls_name: str
    zupanija_name: str


@dataclass(frozen=True)
class CensusSettlement:
    zupanija: str
    jls: str
    naselje: str
    counts: AgeCounts


@dataclass(frozen=True)
class AgeShares:
    ge65: float | None
    lt15: float | None
    source: AgeShareSource | None


def normalize_name(value: str) -> str:
    """Case, dash and spacing differences between DZS and DGU are not real name differences."""
    text = unicodedata.normalize("NFC", value).casefold().replace("–", "-").replace("—", "-")
    text = re.sub(r"\s*-\s*", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def _primary(name: str) -> str:
    """The Croatian part of a bilingual name written as "Buje - Buie"."""
    return re.split(r"\s+[-–—]\s+", name.strip())[0]


def _county(name: str) -> str:
    return normalize_name(re.sub(r"\s+županija$", "", name.strip(), flags=re.IGNORECASE))


def _jls_key(zupanija: str, jls: str) -> tuple[str, str]:
    return _county(zupanija), normalize_name(_primary(jls))


@dataclass(frozen=True)
class SettlementMatch:
    # Census settlement with its register code, or None if it only counts towards the JLS total.
    census: CensusSettlement
    naselje_code: str | None
    jls_code: str


def match_settlements(
    census: list[CensusSettlement], register: list[DguSettlement], crosswalk: dict[str, Any]
) -> list[SettlementMatch]:
    """Match each census settlement to the register. An unexplained miss raises an error."""
    renames = {
        _jls_key(item["zupanija"], item["dzs"]): _jls_key(item["zupanija"], item["dgu"])
        for item in crosswalk["jls_renames"]
    }
    unmatched_ok = {
        (*_jls_key(item["zupanija"], item["jls"]), normalize_name(item["naselje"]))
        for item in crosswalk["settlements_without_dgu_match"]
    }

    jls_codes: dict[tuple[str, str], str] = {}
    full: dict[tuple[str, str, str], str] = {}
    primary: defaultdict[tuple[str, str, str], list[str]] = defaultdict(list)
    for item in register:
        jls_key = _jls_key(item.zupanija_name, item.jls_name)
        jls_codes[jls_key] = item.jls_code
        full[(*jls_key, normalize_name(item.name))] = item.code
        primary[(*jls_key, normalize_name(_primary(item.name)))].append(item.code)

    matches: list[SettlementMatch] = []
    missing: list[str] = []
    for row in census:
        source_key = _jls_key(row.zupanija, row.jls)
        jls_key = renames.get(source_key, source_key)
        jls_code = jls_codes.get(jls_key)
        if jls_code is None:
            missing.append(f"{row.zupanija} / {row.jls}")
            continue
        code = full.get((*jls_key, normalize_name(row.naselje)))
        if code is None:
            candidates = primary.get((*jls_key, normalize_name(_primary(row.naselje))), [])
            code = candidates[0] if len(candidates) == 1 else None
        if code is None and (*source_key, normalize_name(row.naselje)) not in unmatched_ok:
            missing.append(f"{row.zupanija} / {row.jls} / {row.naselje}")
            continue
        matches.append(SettlementMatch(census=row, naselje_code=code, jls_code=jls_code))
    if missing:
        raise ValueError(f"unmatched census names: {sorted(missing)[:20]}")
    return matches


def _share(part: int, total: int) -> float:
    return min(part / total, 1.0)


def age_shares(
    cell_total: int | None,
    cell_ge65: int | None,
    cell_lt15: int | None,
    naselje: AgeCounts | None,
    jls: AgeCounts | None,
    min_cell_pop: int,
) -> AgeShares:
    """Use the cell shares only for larger cells; otherwise the settlement, then the JLS."""
    if not cell_total or cell_total <= 0:
        return AgeShares(None, None, None)
    if cell_total >= min_cell_pop and cell_ge65 is not None and cell_lt15 is not None:
        return AgeShares(_share(cell_ge65, cell_total), _share(cell_lt15, cell_total), "cell")
    if naselje is not None and naselje.total > 0:
        return AgeShares(
            _share(naselje.ge65, naselje.total), _share(naselje.lt15, naselje.total), "naselje"
        )
    if jls is not None and jls.total > 0:
        return AgeShares(_share(jls.ge65, jls.total), _share(jls.lt15, jls.total), "jls")
    return AgeShares(None, None, None)
