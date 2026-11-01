"""DGU addresses (INSPIRE GML in EPSG:3035) → ref.addresses for the geocoder (SPEC §9.7)."""

import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from sqlalchemy import text

from klimakompas.core.db import stage_rows
from klimakompas.core.raw import ensure_raw
from klimakompas.sources.base import LoadResult, RunContext, control, record
from klimakompas.sources.gml import (
    BASE_LOCAL_ID,
    GML,
    GML_ID,
    GN_TEXT,
    XLINK_TITLE,
    href_id,
    iter_elements,
    parse_point,
    to_ewkb,
)

AD = "{http://inspire.ec.europa.eu/schemas/ad/4.0}"
FILENAME = "INSPIRE_Addresses_(AD).zip"
SETTLEMENT_LEVEL = "4thOrder"


@dataclass(frozen=True)
class Address:
    id: str
    label: str
    street: str | None
    house_number: str | None
    naselje_code: str | None
    naselje_name: str | None
    geom_ewkb: str


def parse_street_names(stream: IO[bytes]) -> dict[str, str]:
    return {
        element.get(GML_ID): next(element.iter(GN_TEXT)).text.strip()
        for element in iter_elements(stream, f"{AD}ThoroughfareName")
    }


def parse_settlement_names(stream: IO[bytes]) -> dict[str, tuple[str, str]]:
    """Map AdminUnitName ids to (settlement code, name); the country entry is skipped."""
    names: dict[str, tuple[str, str]] = {}
    for element in iter_elements(stream, f"{AD}AdminUnitName"):
        if element.find(f"{AD}level").get(XLINK_TITLE) == SETTLEMENT_LEVEL:
            names[element.get(GML_ID)] = (
                element.findtext(f"{AD}alternativeIdentifier"),
                next(element.iter(GN_TEXT)).text.strip(),
            )
    return names


def _address(
    element: Any, streets: dict[str, str], settlements: dict[str, tuple[str, str]]
) -> Address:
    street: str | None = None
    code: str | None = None
    settlement: str | None = None
    for component in element.findall(f"{AD}component"):
        reference = href_id(component)
        if reference in streets:
            street = streets[reference]
        elif reference in settlements:
            code, settlement = settlements[reference]
    designator = element.find(
        f"{AD}locator/{AD}AddressLocator/{AD}designator/{AD}LocatorDesignator"
    )
    point = element.find(f"{AD}position/{AD}GeographicPosition/{AD}geometry/{GML}Point")
    return Address(
        id=next(element.iter(BASE_LOCAL_ID)).text,
        label=element.findtext(f"{AD}alternativeIdentifier").strip(),
        street=street,
        house_number=designator.findtext(f"{AD}designator") if designator is not None else None,
        naselje_code=code,
        naselje_name=settlement,
        geom_ewkb=to_ewkb(parse_point(point)),
    )


def parse_addresses(
    stream: IO[bytes], streets: dict[str, str], settlements: dict[str, tuple[str, str]]
) -> Iterator[Address]:
    for element in iter_elements(stream, f"{AD}Address"):
        yield _address(element, streets, settlements)


class DguAdConnector:
    source_id = "dgu_ad"

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

    def parse(self, artifacts: list[Path]) -> Path:
        # The file is too large to hold in memory, so parsing happens while loading.
        return artifacts[0]

    def load(self, frame: Path, ctx: RunContext) -> LoadResult:
        conn = ctx.db
        with zipfile.ZipFile(frame) as archive:
            with archive.open("ThoroughfareName.gml") as stream:
                streets = parse_street_names(stream)
            with archive.open("AdminUnitName.gml") as stream:
                settlements = parse_settlement_names(stream)
            with archive.open("Address.gml") as stream:
                rows = (
                    (
                        a.id,
                        a.label,
                        a.street,
                        a.house_number,
                        a.naselje_code,
                        a.naselje_name,
                        a.geom_ewkb,
                    )
                    for a in parse_addresses(stream, streets, settlements)
                )
                count = stage_rows(
                    conn,
                    "ref.addresses",
                    (
                        "id",
                        "label",
                        "street",
                        "house_number",
                        "naselje_code",
                        "naselje_name",
                        "geom",
                    ),
                    rows,
                )

        # Building the trigram index once after the load is far faster than updating it per row.
        conn.execute(text("SET LOCAL maintenance_work_mem = '512MB'"))
        conn.execute(text("DROP INDEX IF EXISTS ref.addresses_search_idx"))
        conn.execute(
            text(
                "INSERT INTO ref.addresses (id, label, street, house_number, naselje_code, "
                "naselje_name, jls_code, search_text, geom) "
                "SELECT s.id, s.label, s.street, s.house_number, n.code, s.naselje_name, "
                "n.jls_code, ref.normalize_search(s.label), s.geom "
                "FROM _stage s LEFT JOIN ref.naselja n ON n.code = s.naselje_code "
                "ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label, street = EXCLUDED.street, "
                "house_number = EXCLUDED.house_number, naselje_code = EXCLUDED.naselje_code, "
                "naselje_name = EXCLUDED.naselje_name, jls_code = EXCLUDED.jls_code, "
                "search_text = EXCLUDED.search_text, geom = EXCLUDED.geom"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX addresses_search_idx ON ref.addresses "
                "USING gin (search_text gin_trgm_ops)"
            )
        )
        without_jls = conn.execute(
            text("SELECT count(*) FROM ref.addresses WHERE jls_code IS NULL")
        ).scalar_one()
        control(ctx, "addresses_nonempty", min(count, 1), 1)
        record(ctx, "addresses_without_jls", without_jls)
        return LoadResult(rows=count)
