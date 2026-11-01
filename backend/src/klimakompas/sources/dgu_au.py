"""DGU administrative units (INSPIRE GML in EPSG:3035) → ref.zupanije, ref.jls, ref.naselja."""

import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from shapely.geometry import MultiPolygon
from sqlalchemy import text

from klimakompas.core.config import load_thresholds
from klimakompas.core.db import stage_rows, upsert_rows
from klimakompas.core.raw import ensure_raw
from klimakompas.pipeline.grid import build_grid
from klimakompas.sources.base import LoadResult, RunContext, control
from klimakompas.sources.gml import (
    GML,
    GML_ID,
    GN_TEXT,
    XLINK_TITLE,
    href_id,
    iter_elements,
    parse_multisurface,
    to_ewkb,
)

AU = "{http://inspire.ec.europa.eu/schemas/au/4.0}"
LEVELS = {"2ndOrder": "zupanija", "3rdOrder": "jls", "4thOrder": "naselje"}
MEMBER = "AdministrativeUnit.gml"
FILENAME = "INSPIRE_Administrative_Units_(AU).zip"


@dataclass(frozen=True)
class AdminUnit:
    gml_id: str
    code: str
    name: str
    level: str
    upper_id: str | None
    geom: MultiPolygon


def parse_units(stream: IO[bytes]) -> Iterator[AdminUnit]:
    """Keep counties, JLS and settlements. Statistical and census circles are not used."""
    for element in iter_elements(stream, f"{AU}AdministrativeUnit"):
        level = LEVELS.get(element.find(f"{AU}nationalLevel").get(XLINK_TITLE))
        if level is None:
            continue
        upper = element.find(f"{AU}upperLevelUnit")
        yield AdminUnit(
            gml_id=element.get(GML_ID),
            code=element.findtext(f"{AU}nationalCode"),
            name=next(element.iter(GN_TEXT)).text.strip(),
            level=level,
            upper_id=href_id(upper) if upper is not None else None,
            geom=parse_multisurface(element.find(f"{AU}geometry/{GML}MultiSurface")),
        )


class DguAuConnector:
    source_id = "dgu_au"

    def fetch(self, ctx: RunContext) -> list[Path]:
        return [
            ensure_raw(
                ctx.client,
                ctx.data_dir,
                self.source_id,
                FILENAME,
                ctx.source.access["file"],
                ctx.source.license,
            )
        ]

    def parse(self, artifacts: list[Path]) -> list[AdminUnit]:
        with zipfile.ZipFile(artifacts[0]) as archive, archive.open(MEMBER) as stream:
            return list(parse_units(stream))

    def load(self, frame: list[AdminUnit], ctx: RunContext) -> LoadResult:
        conn = ctx.db
        by_id = {unit.gml_id: unit for unit in frame}
        by_level: dict[str, list[AdminUnit]] = {"zupanija": [], "jls": [], "naselje": []}
        for unit in frame:
            by_level[unit.level].append(unit)

        def parent_code(unit: AdminUnit) -> str:
            assert unit.upper_id is not None
            return by_id[unit.upper_id].code

        upsert_rows(
            conn,
            "ref.zupanije",
            ("code", "name", "geom"),
            ("code",),
            ((u.code, u.name, to_ewkb(u.geom)) for u in by_level["zupanija"]),
        )
        # `kind` stays untouched: the DGU register does not have it, the DZS connector sets it.
        upsert_rows(
            conn,
            "ref.jls",
            ("code", "name", "zupanija_code", "geom"),
            ("code",),
            ((u.code, u.name, parent_code(u), to_ewkb(u.geom)) for u in by_level["jls"]),
        )
        stage_rows(
            conn,
            "ref.naselja",
            ("code", "name", "jls_code", "geom"),
            ((u.code, u.name, parent_code(u), to_ewkb(u.geom)) for u in by_level["naselje"]),
        )
        conn.execute(
            text(
                "INSERT INTO ref.naselja (code, name, jls_code, geom, point) "
                "SELECT code, name, jls_code, geom, ST_PointOnSurface(geom) FROM _stage "
                "ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, "
                "jls_code = EXCLUDED.jls_code, geom = EXCLUDED.geom, point = EXCLUDED.point"
            )
        )

        controls = load_thresholds()["controls"]
        control(ctx, "zupanije_count", len(by_level["zupanija"]), controls["zupanije"])
        control(ctx, "jls_count", len(by_level["jls"]), controls["jls"])

        cells = build_grid(conn)
        control(ctx, "grid_cells_nonempty", min(cells, 1), 1)
        return LoadResult(rows=len(frame) + cells)
