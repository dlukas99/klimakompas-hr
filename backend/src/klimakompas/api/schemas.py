"""API response models; the frontend types are generated from these."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    jls_code: str | None = None


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
    used_for: list[str]
    schedule: str | None
    stale_after: str | None
    last_success_at: datetime | None
    last_status: str | None
    state: Literal["ok", "stale", "failed", "static", "browser", "unused"]
    portal_title: str | None
    portal_license: str | None
    portal_modified: datetime | None


class CodeName(BaseModel):
    code: str
    name: str


class JlsRef(CodeName):
    kind: str | None


class CardLocation(BaseModel):
    lat: float
    lon: float
    label: str
    naselje: CodeName
    jls: JlsRef
    zupanija: CodeName
    cell_id: str


class CardIkr(BaseModel):
    value: float | None
    level: int | None
    label: str | None
    percentile: float | None
    index_version: str | None
    populated: bool


class Factor(BaseModel):
    factor: Literal["hazard", "vulnerability", "risk"]
    value: float


class HazardBlock(BaseModel):
    level: int | None
    label: str | None
    h: float | None
    r: float | None
    key_value: dict[str, float | int | bool | None]
    explanation: list[Factor]
    source_ids: list[str]


class CardHazards(BaseModel):
    flood: HazardBlock
    heat: HazardBlock
    fire: HazardBlock
    air: HazardBlock


class CardPopulation(BaseModel):
    total_rounded: int | None
    below_threshold: bool
    share_65plus: float | None
    share_under15: float | None
    age_share_source: str | None
    suppressed: bool


class Warning(BaseModel):
    id: str
    event: str | None
    awareness_type: str | None
    level: int | None
    level_name: str | None
    severity: str | None
    onset: datetime | None
    expires: datetime | None
    area_desc: str | None
    zupanija_code: str | None
    description: str | None
    instruction: str | None
    fetched_at: datetime


class WarningsResponse(BaseModel):
    warnings: list[Warning]
    checked_at: datetime | None


class PollutantValue(BaseModel):
    value: float
    unit: str | None
    observed_at: datetime
    stale: bool
    eaqi_class: int
    eaqi_label: str


class AirStation(BaseModel):
    id: str
    name: str
    network: str | None
    lat: float | None
    lon: float | None
    values: dict[str, PollutantValue]
    eaqi_class: int | None
    eaqi_label: str | None
    observed_at: datetime | None
    stale: bool


class StationRef(BaseModel):
    id: str
    name: str
    distance_km: float


class AirNow(BaseModel):
    station: StationRef
    pollutant: Literal["pm25", "pm10"]
    # local | local_pm10 | nearest_pm25: the UI must say what is shown instead of local PM2.5.
    substitution: Literal["local", "local_pm10", "nearest_pm25"]
    value: PollutantValue
    values: dict[str, PollutantValue]
    observed_at: datetime


class ForecastPoint(BaseModel):
    target_time: datetime
    pm25: float
    lo: float | None
    hi: float | None
    model_version: str


class SeriesPoint(BaseModel):
    ts: datetime
    value: float
    unit: str | None


class FireIndex(BaseModel):
    station_name: str | None
    fwi: float | None
    category: str | None
    index_date: date | None
    in_season: bool
    fetched_at: datetime
    distance_km: float | None


class Heatwave(BaseModel):
    level: str | None
    fetched_at: datetime


class NatureArea(BaseModel):
    layer: str
    name: str | None
    category: str | None
    distance_m: float


class CardLive(BaseModel):
    warnings: list[Warning]
    warnings_checked_at: datetime | None
    air_now: AirNow | None
    air_forecast: list[ForecastPoint]
    fire_index: FireIndex | None
    heatwave: Heatwave | None
    nature_nearby: list[NatureArea]


class AdviceBlock(BaseModel):
    source: str
    url: str
    accessed: date
    items: list[str]


class AreaSummary(BaseModel):
    """The settlement or JLS around the point, with census totals from DZS."""

    code: str
    name: str
    pop: int | None
    pop65: int | None
    ikr_level: int | None
    ikr_label: str | None
    rank_hr: int | None = None
    total_hr: int | None = None


class CardAreas(BaseModel):
    naselje: AreaSummary
    jls: AreaSummary


class LiveStatus(BaseModel):
    source: Literal["dhmz_cap", "azo_aq_rest"]
    # ok | stale: older than expected | missing: never loaded or failed | none_nearby: no station
    state: Literal["ok", "stale", "missing", "none_nearby"]
    checked_at: datetime | None


class CardResponse(BaseModel):
    location: CardLocation
    ikr: CardIkr
    hazards: CardHazards
    population: CardPopulation
    areas: CardAreas
    scope: Literal["point", "naselje", "jls"]
    live: CardLive
    advice: dict[str, AdviceBlock]
    generated_at: datetime
    partial: bool
    degraded_sources: list[str]
    live_status: list[LiveStatus]


class Exposed(BaseModel):
    pop: float
    pop65: float
    share: float


class JlsListItem(BaseModel):
    code: str
    name: str
    kind: str | None
    zupanija_name: str
    pop: int | None
    ikr_popw: float | None
    ikr_class: int | None
    rank_hr: int | None


class Profile(BaseModel):
    flood: float | None
    heat: float | None
    fire: float | None
    air: float | None


class JlsProfiles(BaseModel):
    jls: Profile
    zupanija: Profile
    hr: Profile


class Attention(BaseModel):
    hazard: str
    text: str
    value: int
    url: str | None


class JlsDetail(BaseModel):
    code: str
    name: str
    kind: str | None
    zupanija: CodeName
    pop: int | None
    pop65: int | None
    ikr: float | None
    ikr_class: int | None
    ikr_label: str | None
    rank_hr: int | None
    rank_zup: int | None
    total_hr: int
    total_zup: int
    exposed: dict[str, Exposed]
    lat: float
    lon: float
    bbox: tuple[float, float, float, float]
    profile: JlsProfiles
    attention: list[Attention]
    index_version: str | None


class JlsNaselje(BaseModel):
    code: str
    name: str
    pop: int | None
    ikr: float | None
    ikr_class: int | None
    exposed: dict[str, Exposed] | None


class JlsCell(BaseModel):
    cell_id: str
    # Null below the disclosure threshold of 10 people.
    pop_total: int | None
    ikr: float | None
    ikr_class: int | None
    class_flood: int | None
    class_heat: int | None
    class_fire: int | None
    class_air: int | None
    naselje: str


class RankingItem(BaseModel):
    code: str
    name: str
    kind: str | None
    zupanija_name: str
    pop: int | None
    ikr: float | None
    ikr_class: int | None
    rank_hr: int | None
    rank_zup: int | None
    value: float | None


class Citation(BaseModel):
    n: int
    id: str
    title: str
    publisher: str
    url: str | None
    last_modified: str | None


class QuickAnswer(BaseModel):
    text: str
    citations: list[Citation]
    as_of: str | None


class AgentStatus(BaseModel):
    llm_available: bool


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class QualityRow(BaseModel):
    source_id: str
    check_id: str
    status: Literal["pass", "fail"]
    value: float | None
    details: dict[str, object] | None
    checked_at: datetime


class ExportFile(BaseModel):
    id: str
    title: str
    description: str
    license: str
    files: list[str]
