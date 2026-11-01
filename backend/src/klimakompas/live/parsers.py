"""Pure parsers for the live sources. The shapes were checked against real responses."""

import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from lxml import etree

CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"
PM_MAX = 1000.0


@dataclass(frozen=True)
class CapWarning:
    id: str
    event: str
    awareness_type: str | None
    level: int | None
    level_name: str | None
    severity: str | None
    onset: datetime | None
    expires: datetime | None
    region_id: str | None
    nuts3: str | None
    area_desc: str
    description: str | None
    instruction: str | None


def _cap_time(value: str | None) -> datetime | None:
    """DHMZ writes a space instead of the T in CAP times."""
    if not value:
        return None
    return datetime.fromisoformat(value.strip().replace(" ", "T", 1)).astimezone(UTC)


def _parameter(info: Any, name: str) -> str | None:
    for parameter in info.findall(f"{CAP}parameter"):
        if parameter.findtext(f"{CAP}valueName") == name:
            value: str | None = parameter.findtext(f"{CAP}value")
            return value
    return None


def _geocode(area: Any, name: str) -> str | None:
    for code in area.findall(f"{CAP}geocode"):
        if code.findtext(f"{CAP}valueName") == name:
            value: str | None = code.findtext(f"{CAP}value")
            return value
    return None


def _clean(value: str | None) -> str | None:
    return re.sub(r"\s+", " ", value).strip() if value else None


def parse_cap(body: bytes) -> list[CapWarning]:
    """Croatian blocks only; each CAP info repeats in English. A file may hold no alert at all."""
    root = etree.fromstring(body)
    identifier = root.findtext(f"{CAP}identifier") or ""
    warnings: list[CapWarning] = []
    for position, info in enumerate(root.findall(f"{CAP}info")):
        if info.findtext(f"{CAP}language") != "hr":
            continue
        awareness = (_parameter(info, "awareness_level") or "").split(";")
        kind = (_parameter(info, "awareness_type") or "").split(";")
        for area_position, area in enumerate(info.findall(f"{CAP}area")):
            warnings.append(
                CapWarning(
                    id=f"{identifier}:{position}:{area_position}",
                    event=_clean(info.findtext(f"{CAP}event")) or "",
                    awareness_type=kind[1].strip() if len(kind) > 1 else None,
                    level=int(awareness[0]) if awareness[0].strip().isdigit() else None,
                    level_name=awareness[1].strip() if len(awareness) > 1 else None,
                    severity=info.findtext(f"{CAP}severity"),
                    onset=_cap_time(info.findtext(f"{CAP}onset")),
                    expires=_cap_time(info.findtext(f"{CAP}expires")),
                    region_id=_geocode(area, "EMMA_ID"),
                    nuts3=_geocode(area, "NUTS3"),
                    area_desc=(area.findtext(f"{CAP}areaDesc") or "").strip(),
                    description=_clean(info.findtext(f"{CAP}description")),
                    instruction=_clean(info.findtext(f"{CAP}instruction")),
                )
            )
    return warnings


def county_key(name: str) -> str:
    text = unicodedata.normalize("NFC", name).casefold()
    return re.sub(r"\s+županija$", "", text.strip())


@dataclass(frozen=True)
class FireStation:
    code: str
    name: str
    fwi: float | None
    category: str | None


def parse_fire_index(body: bytes) -> tuple[date | None, list[FireStation]]:
    root = etree.fromstring(body)
    raw_date = (root.findtext("datum") or "").strip().rstrip(".")
    day = datetime.strptime(raw_date, "%d.%m.%Y").date() if raw_date else None
    stations = []
    for item in root.findall("postaja"):
        fwi = (item.findtext("fwi") or "").strip()
        stations.append(
            FireStation(
                code=(item.findtext("code") or "").strip(),
                name=(item.findtext("ime") or "").strip(),
                fwi=float(fwi.replace(",", ".")) if fwi else None,
                category=(item.findtext("indeks") or "").strip() or None,
            )
        )
    return day, stations


def parse_k1_hot_days(body: bytes) -> float:
    """Mean yearly days with Tmax >= 30 °C from a DHMZ climate table (the sum of its months)."""
    root = etree.fromstring(body)
    for row in root.findall("podaci"):
        label = html.unescape(row.findtext("el") or "")
        if label.startswith("vrućih"):
            return float(sum(float(item.text) for item in row.findall("mj")))
    raise ValueError("no hot-day row in the DHMZ climate table")


def parse_heatwave(body: bytes) -> dict[str, Any]:
    """Out of season the file has an empty section; the active shape is still TODO(verify)."""
    root = etree.fromstring(body)
    section = root.find(".//section")
    text = " ".join("".join(section.itertext()).split()) if section is not None else ""
    return {"active": bool(text), "text": text}


@dataclass(frozen=True)
class AqObservation:
    ts: datetime
    value: float
    unit: str | None


def parse_aq(records: list[dict[str, Any]]) -> list[AqObservation]:
    """Flat records with the time as epoch milliseconds; out-of-range values are dropped."""
    observations = []
    for record in records:
        value = record.get("vrijednost")
        timestamp = record.get("vrijeme")
        if value is None or timestamp is None or not 0 <= float(value) <= PM_MAX:
            continue
        observations.append(
            AqObservation(
                ts=datetime.fromtimestamp(int(timestamp) / 1000, UTC),
                value=float(value),
                unit=record.get("mjernaJedinica"),
            )
        )
    return observations


def _station_key(name: str) -> str:
    return re.sub(r"[\s\-–]+", " ", unicodedata.normalize("NFC", name).casefold()).strip()


def _decimal(value: str | None) -> float | None:
    return float(value.replace(",", ".")) if value else None


@dataclass(frozen=True)
class AqStation:
    id: str
    name: str
    network: str | None
    lat: float | None
    lon: float | None


def parse_stations(form: dict[str, Any], coordinates: dict[str, Any]) -> list[AqStation]:
    """Station ids come from the data form and positions from the coordinates table."""
    positions: dict[str, tuple[str | None, float | None, float | None]] = {}
    for row in coordinates["data"]:
        positions[_station_key(row[1])] = (row[0], _decimal(row[11]), _decimal(row[12]))
    stations = []
    for station_id, name in form["options"][0]:
        network, lat, lon = positions.get(_station_key(name), (None, None, None))
        stations.append(AqStation(str(station_id), name.strip(), network, lat, lon))
    return stations


def eaqi_class(value: float, bands: list[float]) -> int:
    """Class 1-6: the first upper limit the value does not exceed. Rounded as in the EEA table."""
    rounded = round(value)
    for position, limit in enumerate(bands, start=1):
        if rounded <= limit:
            return position
    return len(bands) + 1
