"""FastAPI application (SPEC §12). Run with --no-access-log: queries must not reach the logs."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

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
