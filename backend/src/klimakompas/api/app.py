"""FastAPI application (SPEC §12). Run with --no-access-log: queries must not reach the logs."""

import json
import time
from collections.abc import Iterator
from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from klimakompas.agent.quick import QuickId, quick_answer
from klimakompas.agent.runner import (
    LlmUnavailableError,
    OpenAiCompatibleClient,
    llm_available,
    run_agent,
)
from klimakompas.agent.structured import run_structured
from klimakompas.api import data
from klimakompas.api.geocode import geocode
from klimakompas.api.schemas import (
    AgentStatus,
    AirStation,
    CardResponse,
    ChatRequest,
    ExportFile,
    ForecastPoint,
    GeocodeResponse,
    Health,
    JlsCell,
    JlsDetail,
    JlsListItem,
    JlsNaselje,
    NatureArea,
    QualityRow,
    QuickAnswer,
    RankingItem,
    Ready,
    SeriesPoint,
    SourceInfo,
    WarningsResponse,
)
from klimakompas.core.config import get_settings
from klimakompas.core.db import get_engine
from klimakompas.quality.exports import DATASETS, EXPORT_DIR, EXPORT_FILES
from klimakompas.quality.report import list_checks

API_PREFIX = "/api/v1"
RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_MAX_CLIENTS = 10_000
PROBLEM_TYPE = "application/problem+json"


def get_connection() -> Iterator[Connection]:
    try:
        with get_engine().connect() as conn:
            yield conn
    except SQLAlchemyError as error:
        # The exception text can contain the query, so it is not passed on.
        raise HTTPException(status_code=503, detail="Baza podataka nije dostupna.") from error


Db = Annotated[Connection, Depends(get_connection)]


def _problem(status: int, title: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        {"type": "about:blank", "title": title, "status": status, "detail": detail},
        status_code=status,
        media_type=PROBLEM_TYPE,
    )


class RateLimiter:
    """Fixed one-minute window per client, in memory (SPEC §10.5)."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.counts: dict[str, tuple[int, int]] = {}

    def allow(self, client: str, now: float | None = None) -> bool:
        minute = int((now if now is not None else time.time()) // 60)
        if len(self.counts) > RATE_LIMIT_MAX_CLIENTS:
            self.counts.clear()
        seen_minute, count = self.counts.get(client, (minute, 0))
        count = count + 1 if seen_minute == minute else 1
        self.counts[client] = (minute, count)
        return count <= self.limit


_rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chat_events(message: str) -> Iterator[str]:
    """The conversation is not stored; only this stream carries it."""
    try:
        with get_engine().connect() as conn:
            settings = get_settings()
            llm = OpenAiCompatibleClient(settings)
            run = run_agent if settings.llm_mode == "tools" else run_structured
            for item in run(conn, llm, message):
                if item["event"] == "tool":
                    yield _sse("tool", {"name": item["name"]})
                else:
                    yield _sse("answer", asdict(item["result"]))
    except (LlmUnavailableError, SQLAlchemyError):
        yield _sse("unavailable", {})


def _catalog_file(name: str, media_type: str) -> FileResponse:
    path = EXPORT_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Katalog još nije izrađen.")
    return FileResponse(path, media_type=media_type)


def create_app() -> FastAPI:
    app = FastAPI(
        title="KlimaKompas HR API",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in get_settings().cors_origins.split(",")],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_problem(_: Request, error: StarletteHTTPException) -> JSONResponse:
        return _problem(error.status_code, str(error.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_problem(_: Request, __: RequestValidationError) -> JSONResponse:
        # Validation details echo the input, so a search query never comes back in an error.
        return _problem(422, "Neispravan zahtjev.")

    @app.get(f"{API_PREFIX}/health")
    def health() -> Health:
        return Health(status="ok")

    @app.get(f"{API_PREFIX}/ready")
    def ready(conn: Db) -> Ready:
        last = conn.execute(
            text("SELECT max(last_success_at) FROM meta.sources WHERE last_status = 'success'")
        ).scalar_one()
        return Ready(status="ready" if last else "degraded", database=True, last_etl_at=last)

    @app.get(f"{API_PREFIX}/geocode")
    def geocode_endpoint(
        conn: Db,
        q: Annotated[str, Query(min_length=2, max_length=120)],
        limit: Annotated[int, Query(ge=1, le=20)] = 8,
    ) -> GeocodeResponse:
        return geocode(conn, q, limit)

    @app.get(f"{API_PREFIX}/card")
    def card(
        conn: Db,
        lat: Annotated[float, Query(ge=42.0, le=47.0)],
        lon: Annotated[float, Query(ge=13.0, le=20.0)],
        label: Annotated[str | None, Query(max_length=200)] = None,
    ) -> CardResponse:
        result = data.build_card(conn, lat, lon, label=label)
        if result is None:
            raise HTTPException(status_code=404, detail="Lokacija je izvan područja Hrvatske.")
        return CardResponse.model_validate(result)

    @app.get(f"{API_PREFIX}/jls")
    def jls_list(conn: Db) -> list[JlsListItem]:
        return [JlsListItem.model_validate(row) for row in data.list_jls(conn)]

    @app.get(f"{API_PREFIX}/jls/{{code}}")
    def jls_one(conn: Db, code: str) -> JlsDetail:
        result = data.jls_detail(conn, code)
        if result is None:
            raise HTTPException(status_code=404, detail="Općina ili grad nije pronađen.")
        return JlsDetail.model_validate(result)

    @app.get(f"{API_PREFIX}/jls/{{code}}/naselja")
    def jls_settlements(conn: Db, code: str) -> list[JlsNaselje]:
        return [JlsNaselje.model_validate(row) for row in data.jls_naselja(conn, code)]

    @app.get(f"{API_PREFIX}/jls/{{code}}/cells")
    def jls_grid(conn: Db, code: str) -> list[JlsCell]:
        return [JlsCell.model_validate(row) for row in data.jls_cells(conn, code)]

    @app.get(f"{API_PREFIX}/rankings")
    def rankings(
        conn: Db,
        metric: Literal["ikr", "exposed", "exposed_share"] = "ikr",
        hazard: Literal["flood", "heat", "fire", "air"] | None = None,
        zupanija: str | None = None,
        limit: Annotated[int, Query(ge=1, le=556)] = 20,
    ) -> list[RankingItem]:
        if metric != "ikr" and hazard is None:
            raise HTTPException(status_code=422, detail="Za ovu mjeru odaberite opasnost.")
        rows = data.rankings(conn, hazard, metric, zupanija, limit)
        return [RankingItem.model_validate(row) for row in rows]

    @app.get(f"{API_PREFIX}/warnings/active")
    def warnings_active(
        conn: Db,
        lat: Annotated[float | None, Query(ge=42.0, le=47.0)] = None,
        lon: Annotated[float | None, Query(ge=13.0, le=20.0)] = None,
        region: str | None = None,
    ) -> WarningsResponse:
        zupanija = region
        if lat is not None and lon is not None:
            zupanija = conn.execute(
                text("SELECT zupanija_code FROM ref.grid_1km WHERE cell_id = :id"),
                {"id": data.cell_id_at(lat, lon)},
            ).scalar_one_or_none()
            if zupanija is None:
                raise HTTPException(status_code=404, detail="Lokacija je izvan područja Hrvatske.")
        status = data.source_status(conn, "dhmz_cap")
        return WarningsResponse.model_validate(
            {
                "warnings": data.active_warnings(conn, zupanija),
                "checked_at": status.last_success_at if status else None,
            }
        )

    @app.get(f"{API_PREFIX}/air/stations")
    def air_stations(conn: Db) -> list[AirStation]:
        return [AirStation.model_validate(row) for row in data.station_latest(conn)]

    @app.get(f"{API_PREFIX}/air/stations/{{station_id}}/series")
    def air_series(
        conn: Db,
        station_id: str,
        pollutant: Literal["pm25", "pm10", "no2", "o3"] = "pm25",
        hours: Annotated[int, Query(ge=1, le=720)] = 48,
    ) -> list[SeriesPoint]:
        rows = data.station_series(conn, station_id, pollutant, hours)
        return [SeriesPoint.model_validate(row) for row in rows]

    @app.get(f"{API_PREFIX}/air/stations/{{station_id}}/forecast")
    def air_forecast(conn: Db, station_id: str) -> list[ForecastPoint]:
        return [ForecastPoint.model_validate(row) for row in data.latest_forecast(conn, station_id)]

    @app.get(f"{API_PREFIX}/nature/nearby")
    def nature(
        conn: Db,
        lat: Annotated[float, Query(ge=42.0, le=47.0)],
        lon: Annotated[float, Query(ge=13.0, le=20.0)],
        radius_m: Annotated[int, Query(ge=100, le=20000)] = 1000,
    ) -> list[NatureArea]:
        return [
            NatureArea.model_validate(row) for row in data.nature_nearby(conn, lat, lon, radius_m)
        ]

    @app.get(f"{API_PREFIX}/agent/status")
    def agent_status() -> AgentStatus:
        return AgentStatus(llm_available=llm_available(get_settings()))

    @app.get(f"{API_PREFIX}/agent/quick")
    def agent_quick(
        conn: Db,
        question: QuickId,
        jls: Annotated[str | None, Query(max_length=120)] = None,
        lat: Annotated[float | None, Query(ge=42.0, le=47.0)] = None,
        lon: Annotated[float | None, Query(ge=13.0, le=20.0)] = None,
    ) -> QuickAnswer:
        return QuickAnswer.model_validate(quick_answer(conn, question, jls, lat, lon))

    @app.post(f"{API_PREFIX}/agent/chat")
    def agent_chat(request: Request, body: ChatRequest) -> StreamingResponse:
        # The address is used only for this in-memory counter and is never stored or logged.
        client = request.headers.get(
            "x-forwarded-for", request.client.host if request.client else ""
        )
        if not _rate_limiter.allow(client.split(",")[0].strip()):
            raise HTTPException(status_code=429, detail="Previše zahtjeva. Pokušajte za minutu.")
        return StreamingResponse(_chat_events(body.message), media_type="text/event-stream")

    @app.get(f"{API_PREFIX}/quality")
    def quality(conn: Db) -> list[QualityRow]:
        return [QualityRow.model_validate(row) for row in list_checks(conn)]

    @app.get(f"{API_PREFIX}/export/{{filename}}")
    def export_file(filename: str) -> FileResponse:
        # Only the published names can be served, so the path cannot leave the export folder.
        path = EXPORT_DIR / filename
        if filename not in EXPORT_FILES or not path.exists():
            raise HTTPException(status_code=404, detail="Skup nije pronađen.")
        return FileResponse(path, filename=filename)

    @app.get(f"{API_PREFIX}/exports")
    def exports() -> list[ExportFile]:
        return [
            ExportFile(
                id=dataset.id,
                title=dataset.title_hr,
                description=dataset.description_hr,
                license=dataset.license_url,
                files=[
                    f"{dataset.id}.{extension}"
                    for extension in dataset.formats
                    if (EXPORT_DIR / f"{dataset.id}.{extension}").exists()
                ],
            )
            for dataset in DATASETS
        ]

    @app.get(f"{API_PREFIX}/catalog.ttl")
    def catalog_ttl() -> FileResponse:
        return _catalog_file("catalog.ttl", "text/turtle")

    @app.get(f"{API_PREFIX}/catalog.jsonld")
    def catalog_jsonld() -> FileResponse:
        return _catalog_file("catalog.jsonld", "application/ld+json")

    @app.get(f"{API_PREFIX}/sources")
    def sources(conn: Db) -> list[SourceInfo]:
        return [SourceInfo.model_validate(row) for row in data.list_sources(conn)]

    return app


app = create_app()
