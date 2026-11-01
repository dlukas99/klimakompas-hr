"""DZS Census 2021 by settlement → pop.naselja_2021, pop.jls_2021 and ref.jls.kind."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from sqlalchemy import text

from klimakompas.core.config import load_crosswalk, load_thresholds
from klimakompas.core.db import upsert_rows
from klimakompas.core.raw import ensure_raw
from klimakompas.pipeline.population import (
    AgeCounts,
    CensusSettlement,
    DguSettlement,
    SettlementMatch,
    match_settlements,
)
from klimakompas.sources.base import LoadResult, RunContext, control

FILENAME = "popis_2021-stanovnistvo_po_naseljima.xlsx"
SHEET = "1."
ZAGREB = "Grad Zagreb"
UNDER_15 = ("0 – 4", "5 – 9", "10 – 14")
OVER_65 = ("65 – 69", "70 – 74", "75 – 79", "80 – 84", "85 – 89", "90 – 94", "95 i više")
KINDS = {"Grad": "grad", "Općina": "opcina"}


@dataclass(frozen=True)
class DzsTable:
    settlements: list[CensusSettlement]
    # Printed JLS rows, keyed by (county, JLS name): counts and kind, used to verify the sums.
    jls: dict[tuple[str, str], tuple[AgeCounts, str]]
    national: AgeCounts


def _number(value: object) -> int:
    """The table writes "-" for "no occurrence"."""
    return 0 if value in (None, "-") else int(str(value))


def parse_table(path: Path) -> DzsTable:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = workbook[SHEET].iter_rows(values_only=True)

    index: dict[str, int] = {}
    settlements: list[CensusSettlement] = []
    jls: dict[tuple[str, str], tuple[AgeCounts, str]] = {}
    national: AgeCounts | None = None
    for row in rows:
        if not index:
            if row[0] == "Županija":
                index = {str(name).split("\n")[0].strip(): i for i, name in enumerate(row) if name}
            continue
        if row[index["Spol"]] != "sv.":
            continue
        counts = AgeCounts(
            total=_number(row[index["Ukupno"]]),
            ge65=sum(_number(row[index[name]]) for name in OVER_65),
            lt15=sum(_number(row[index[name]]) for name in UNDER_15),
        )
        county = str(row[0]).strip()
        kind = row[index["Jedinica lokalne samouprave"]]
        town = row[index["Grad/općina"]]
        settlement = row[index["Naselje"]]
        if settlement:
            # Zagreb is a county and a town at once, so its rows have no JLS name.
            jls_name = str(town).strip() if town else ZAGREB
            settlements.append(CensusSettlement(county, jls_name, str(settlement).strip(), counts))
        elif town:
            jls[(county, str(town).strip())] = (counts, KINDS[str(kind).strip()])
        elif county == ZAGREB:
            jls[(county, ZAGREB)] = (counts, "grad")
        elif county == "Republika Hrvatska":
            national = counts
    workbook.close()
    if not index or national is None:
        raise ValueError("unexpected layout in the DZS workbook")
    return DzsTable(settlements, jls, national)


def aggregate(counts: Iterable[AgeCounts]) -> AgeCounts:
    items = list(counts)
    return AgeCounts(
        total=sum(item.total for item in items),
        ge65=sum(item.ge65 for item in items),
        lt15=sum(item.lt15 for item in items),
    )


def _load_register(ctx: RunContext) -> list[DguSettlement]:
    rows = ctx.db.execute(
        text(
            "SELECT n.code, n.name, n.jls_code, j.name, z.name FROM ref.naselja n "
            "JOIN ref.jls j ON j.code = n.jls_code "
            "JOIN ref.zupanije z ON z.code = j.zupanija_code"
        )
    ).all()
    return [DguSettlement(*row) for row in rows]


class DzsNaseljaConnector:
    source_id = "dzs_naselja_2021"

    def fetch(self, ctx: RunContext) -> list[Path]:
        return [
            ensure_raw(
                ctx.client,
                ctx.data_dir,
                self.source_id,
                FILENAME,
                ctx.source.access["urls"][0],
                ctx.source.license,
            )
        ]

    def parse(self, artifacts: list[Path]) -> DzsTable:
        return parse_table(artifacts[0])

    def load(self, frame: DzsTable, ctx: RunContext) -> LoadResult:
        conn = ctx.db
        register = _load_register(ctx)
        matches = match_settlements(frame.settlements, register, load_crosswalk("dzs_dgu_naselja"))

        by_jls: defaultdict[str, list[SettlementMatch]] = defaultdict(list)
        for match in matches:
            by_jls[match.jls_code].append(match)

        upsert_rows(
            conn,
            "pop.naselja_2021",
            ("naselje_code", "pop_total", "pop_ge65", "pop_lt15"),
            ("naselje_code",),
            (
                (m.naselje_code, m.census.counts.total, m.census.counts.ge65, m.census.counts.lt15)
                for m in matches
                if m.naselje_code is not None
            ),
        )
        totals = {code: aggregate(m.census.counts for m in items) for code, items in by_jls.items()}
        upsert_rows(
            conn,
            "pop.jls_2021",
            ("jls_code", "pop_total", "pop_ge65", "pop_lt15"),
            ("jls_code",),
            ((code, c.total, c.ge65, c.lt15) for code, c in totals.items()),
        )

        # The printed JLS rows must equal the settlement sums; this also carries town/municipality.
        mismatched = 0
        for match_code, items in by_jls.items():
            first = items[0].census
            printed, kind = frame.jls[(first.zupanija, first.jls)]
            mismatched += printed != totals[match_code]
            conn.execute(
                text("UPDATE ref.jls SET kind = :kind WHERE code = :code"),
                {"kind": kind, "code": match_code},
            )

        controls = load_thresholds()["controls"]
        national = aggregate(m.census.counts for m in matches)
        kinds = [kind for _, kind in frame.jls.values()]
        control(ctx, "settlement_sum_total", national.total, controls["pop_total"])
        control(ctx, "settlement_sum_ge65", national.ge65, controls["pop_ge65"])
        control(ctx, "settlement_sum_lt15", national.lt15, controls["pop_lt15"])
        control(ctx, "national_row_total", frame.national.total, controls["pop_total"])
        control(ctx, "jls_rows_equal_settlement_sums", mismatched, 0)
        control(ctx, "gradovi_count", kinds.count("grad"), controls["gradovi"])
        control(ctx, "opcine_count", kinds.count("opcina"), controls["opcine"])
        control(ctx, "jls_with_population", len(totals), controls["jls"])
        return LoadResult(rows=len(matches))
