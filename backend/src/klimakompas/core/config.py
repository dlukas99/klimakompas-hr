"""Settings from .env and typed access to config/*.yaml."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_USER_AGENT = "KlimaKompasHR/0.1 (+https://github.com/dlukas99/klimakompas-hr)"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    kk_user_agent: str = DEFAULT_USER_AGENT
    cdsapi_url: str = "https://cds.climate.copernicus.eu/api"
    cdsapi_key: SecretStr = SecretStr("")
    log_level: str = "INFO"


class CountSpec(BaseModel):
    """How to count records in a probe response."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["xml_tag", "json_list", "json_value", "zip_entries"]
    tag: str | None = None
    path: str | None = None


class Probe(BaseModel):
    """One request made by `kk sources verify`."""

    model_config = ConfigDict(extra="forbid")

    url: str
    method: Literal["GET", "HEAD", "RANGE", "ZIP"] = "GET"
    count: CountSpec | None = None
    fixture: str | None = None
    expect_empty_ok: bool = False


class VerifyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # auto: probes run when robots.txt allows them.
    # robots_only: only robots.txt is fetched; the source must not be requested by the server.
    # manual: needs a human step or a browser, so only robots.txt is fetched.
    # api_terms: documented API used under its own terms, as recorded in an ADR. robots.txt is
    # reported but does not block probes.
    policy: Literal["auto", "robots_only", "manual", "api_terms"] = "auto"
    robots_hosts: list[str] = Field(default_factory=list)
    portal_query: str | None = None
    probes: list[Probe] = Field(default_factory=list)


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["verified", "partial", "unverified", "blocked"]
    date: date
    note: str | None = None


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    publisher: str
    data_gov_hr_id: str | None = None
    landing_url: str | None = None
    docs_url: str | None = None
    access: dict[str, Any]
    format: str
    license: str
    attribution: str
    citation: str | None = None
    schedule: str | None = None
    stale_after: str | None = None
    robots_allowed: bool | str = "TODO(verify)"
    used_for: list[str]
    priority: Literal["P0", "P0/P1", "P1", "P2"]
    verification: Verification
    fallback: str | None = None
    verify: VerifyPlan = Field(default_factory=VerifyPlan)


def _load_yaml(name: str) -> Any:
    with (ROOT / "config" / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_sources() -> list[Source]:
    return [Source.model_validate(entry) for entry in _load_yaml("sources.yaml")]


def load_index_config() -> dict[str, Any]:
    config: dict[str, Any] = _load_yaml("index.yaml")
    return config


def load_thresholds() -> dict[str, Any]:
    config: dict[str, Any] = _load_yaml("thresholds.yaml")
    return config


@lru_cache
def get_settings() -> Settings:
    return Settings()
