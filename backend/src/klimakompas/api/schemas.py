"""API response models."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]


class Ready(BaseModel):
    status: Literal["ready", "degraded"]
    database: bool
    last_etl_at: datetime | None


class GeocodeResult(BaseModel):
    kind: Literal["address", "settlement", "municipality"]
    code: str | None
    label: str
    detail: str | None
    lat: float
    lon: float
    # [west, south, east, north] for areas, so the map can fit them; null for addresses.
    bbox: tuple[float, float, float, float] | None
    population: int | None


class GeocodeResponse(BaseModel):
    results: list[GeocodeResult]
    # False when address search was skipped or timed out and only names were searched.
    addresses_searched: bool


class SourceInfo(BaseModel):
    id: str
    name: str
    publisher: str
    license: str
    attribution: str
    landing_url: str | None
    priority: str
    verified_on: date
    last_success_at: datetime | None
    last_status: str | None
