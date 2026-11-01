"""FastAPI application (SPEC §12). Run with --no-access-log: queries must not reach the logs."""

from collections.abc import Iterator
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from klimakompas.api import data
from klimakompas.api.geocode import geocode
from klimakompas.api.schemas import GeocodeResponse, Health, Ready, SourceInfo
from klimakompas.core.config import get_settings, load_sources
from klimakompas.core.db import get_engine

API_PREFIX = "/api/v1"
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
        allow_methods=["GET"],
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
    ) -> dict[str, Any]:
        result = data.build_card(conn, lat, lon, label=label)
        if result is None:
            raise HTTPException(status_code=404, detail="Lokacija je izvan područja Hrvatske.")
        return result

    @app.get(f"{API_PREFIX}/jls")
    def jls_list(conn: Db) -> list[dict[str, Any]]:
        return data.list_jls(conn)

    @app.get(f"{API_PREFIX}/jls/{{code}}")
    def jls_one(conn: Db, code: str) -> dict[str, Any]:
        result = data.jls_detail(conn, code)
        if result is None:
            raise HTTPException(status_code=404, detail="Općina ili grad nije pronađen.")
        return result

    @app.get(f"{API_PREFIX}/jls/{{code}}/naselja")
    def jls_settlements(conn: Db, code: str) -> list[dict[str, Any]]:
        return data.jls_naselja(conn, code)

    @app.get(f"{API_PREFIX}/jls/{{code}}/cells")
    def jls_grid(conn: Db, code: str) -> list[dict[str, Any]]:
        return data.jls_cells(conn, code)

    @app.get(f"{API_PREFIX}/rankings")
    def rankings(
        conn: Db,
        metric: Literal["ikr", "exposed", "exposed_share"] = "ikr",
        hazard: Literal["flood", "heat", "fire", "air"] | None = None,
        zupanija: str | None = None,
        limit: Annotated[int, Query(ge=1, le=556)] = 20,
    ) -> list[dict[str, Any]]:
        if metric != "ikr" and hazard is None:
            raise HTTPException(status_code=422, detail="Za ovu mjeru odaberite opasnost.")
        return data.rankings(conn, hazard, metric, zupanija, limit)

    @app.get(f"{API_PREFIX}/warnings/active")
    def warnings_active(
        conn: Db,
        lat: Annotated[float | None, Query(ge=42.0, le=47.0)] = None,
        lon: Annotated[float | None, Query(ge=13.0, le=20.0)] = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        zupanija = region
        if lat is not None and lon is not None:
            zupanija = conn.execute(
                text("SELECT zupanija_code FROM ref.grid_1km WHERE cell_id = :id"),
                {"id": data.cell_id_at(lat, lon)},
            ).scalar_one_or_none()
            if zupanija is None:
                raise HTTPException(status_code=404, detail="Lokacija je izvan područja Hrvatske.")
        status = data.source_status(conn, "dhmz_cap")
        return {
            "warnings": data.active_warnings(conn, zupanija),
            "checked_at": status.last_success_at if status else None,
        }

    @app.get(f"{API_PREFIX}/air/stations")
    def air_stations(conn: Db) -> list[dict[str, Any]]:
        return data.station_latest(conn)

    @app.get(f"{API_PREFIX}/air/stations/{{station_id}}/series")
    def air_series(
        conn: Db,
        station_id: str,
        pollutant: Literal["pm25", "pm10", "no2", "o3"] = "pm25",
        hours: Annotated[int, Query(ge=1, le=720)] = 48,
    ) -> list[dict[str, Any]]:
        return data.station_series(conn, station_id, pollutant, hours)

    @app.get(f"{API_PREFIX}/air/stations/{{station_id}}/forecast")
    def air_forecast(conn: Db, station_id: str) -> list[dict[str, Any]]:
        return data.latest_forecast(conn, station_id)

    @app.get(f"{API_PREFIX}/nature/nearby")
    def nature(
        conn: Db,
        lat: Annotated[float, Query(ge=42.0, le=47.0)],
        lon: Annotated[float, Query(ge=13.0, le=20.0)],
        radius_m: Annotated[int, Query(ge=100, le=20000)] = 1000,
    ) -> list[dict[str, Any]]:
        return data.nature_nearby(conn, lat, lon, radius_m)

    @app.get(f"{API_PREFIX}/sources")
    def sources(conn: Db) -> list[SourceInfo]:
        status = {
            row.source_id: row
            for row in conn.execute(
                text("SELECT source_id, last_success_at, last_status FROM meta.sources")
            )
        }
        result = []
        for source in load_sources():
            row = status.get(source.id)
            result.append(
                SourceInfo(
                    id=source.id,
                    name=source.name,
                    publisher=source.publisher,
                    license=source.license,
                    attribution=source.attribution,
                    landing_url=source.landing_url,
                    priority=source.priority,
                    verified_on=source.verification.date,
                    last_success_at=row.last_success_at if row else None,
                    last_status=row.last_status if row else None,
                )
            )
        return result

    return app


app = create_app()
