"""Eurostat Census 2021 grid V3 → pop.grid_2021, with age shares per ADR 0005."""

import csv
import io
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from sqlalchemy import text

from klimakompas.core.config import load_thresholds
from klimakompas.core.db import upsert_rows
from klimakompas.core.raw import ensure_raw
from klimakompas.pipeline.grid import add_populated_cells_outside
from klimakompas.pipeline.population import AgeCounts, age_shares
from klimakompas.sources.base import LoadResult, RunContext, control, record

FILENAME = "Eurostat_Census-GRID_2021_V3.zip"
MEMBER = "Eurostat_Census-GRID_2021_V3/ESTAT_Census_2021_V3.csv"
COUNTRY = "HR"
# read.me V3: -8888 is confidential, -9999 is not available for other reasons.
CONFIDENTIAL = {-8888, -9999}


@dataclass(frozen=True)
class CensusCell:
    cell_id: str
    cntr_id: str
    total: int | None
    ge65: int | None
    lt15: int | None

    @property
    def suppressed(self) -> bool:
        return self.total is None or self.ge65 is None or self.lt15 is None


def _value(text_value: str) -> int | None:
    value = int(float(text_value))
    return None if value in CONFIDENTIAL else value


def parse_cells(stream: IO[bytes]) -> Iterator[CensusCell]:
    """Keep cells reported by Croatia, including those shared with a neighbouring country."""
    wrapper = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
    for row in csv.DictReader(wrapper):
        countries = row["CNTR_ID"].split("-")
        if COUNTRY in countries:
            yield CensusCell(
                cell_id=row["GRD_ID"],
                cntr_id=row["CNTR_ID"],
                total=_value(row["T"]),
                ge65=_value(row["Y_GE65"]),
                lt15=_value(row["Y_LT15"]),
            )


def _counts(rows: Iterable[tuple[str, int, int, int]]) -> dict[str, AgeCounts]:
    return {code: AgeCounts(total, ge65, lt15) for code, total, ge65, lt15 in rows}


class EstatCensusConnector:
    source_id = "estat_census_grid_2021"

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

    def parse(self, artifacts: list[Path]) -> list[CensusCell]:
        with zipfile.ZipFile(artifacts[0]) as archive, archive.open(MEMBER) as stream:
            return list(parse_cells(stream))

    def load(self, frame: list[CensusCell], ctx: RunContext) -> LoadResult:
        conn = ctx.db
        min_cell_pop = load_thresholds()["population"]["min_cell_pop_for_age_shares"]
        grid: dict[str, str] = dict(
            conn.execute(text("SELECT cell_id, naselje_code FROM ref.grid_1km")).tuples().all()
        )
        if not grid:
            raise ValueError("ref.grid_1km is empty: run dgu_au first")

        outside = [c.cell_id for c in frame if c.cell_id not in grid and (c.total or 0) > 0]
        added = add_populated_cells_outside(conn, outside)
        grid = dict(
            conn.execute(text("SELECT cell_id, naselje_code FROM ref.grid_1km")).tuples().all()
        )
        cell_jls: dict[str, str] = dict(
            conn.execute(text("SELECT cell_id, jls_code FROM ref.grid_1km")).tuples().all()
        )

        naselja = _counts(
            conn.execute(
                text("SELECT naselje_code, pop_total, pop_ge65, pop_lt15 FROM pop.naselja_2021")
            ).tuples()
        )
        jls = _counts(
            conn.execute(
                text("SELECT jls_code, pop_total, pop_ge65, pop_lt15 FROM pop.jls_2021")
            ).tuples()
        )
        if not naselja or not jls:
            raise ValueError("pop tables are empty: run dzs_naselja_2021 first")

        rows = []
        for cell in frame:
            if cell.cell_id not in grid:
                continue
            shares = age_shares(
                cell.total,
                cell.ge65,
                cell.lt15,
                naselja.get(grid[cell.cell_id]),
                jls.get(cell_jls[cell.cell_id]),
                min_cell_pop,
            )
            rows.append(
                (
                    cell.cell_id,
                    cell.cntr_id,
                    cell.total,
                    cell.ge65,
                    cell.lt15,
                    cell.suppressed,
                    shares.ge65,
                    shares.lt15,
                    shares.source,
                )
            )
        count = upsert_rows(
            conn,
            "pop.grid_2021",
            (
                "cell_id",
                "cntr_id",
                "pop_total",
                "pop_ge65",
                "pop_lt15",
                "suppressed",
                "share_ge65",
                "share_lt15",
                "age_share_source",
            ),
            ("cell_id",),
            rows,
        )

        controls = load_thresholds()["controls"]
        total = conn.execute(text("SELECT sum(pop_total) FROM pop.grid_2021")).scalar_one()
        unassigned = sum(1 for c in frame if (c.total or 0) > 0 and c.cell_id not in grid)
        control(
            ctx,
            "grid_total_vs_census",
            int(total),
            controls["pop_total"],
            controls["grid_tolerance"],
        )
        control(ctx, "populated_cells_without_jls", unassigned, 0)
        record(ctx, "populated_cells_outside_polygons", added)
        return LoadResult(rows=count)
