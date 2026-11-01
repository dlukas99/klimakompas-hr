"""Connector interface and the run wrapper that records every ETL run (SPEC §14)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import structlog
from pydantic import BaseModel
from sqlalchemy import Connection, Engine, text

from klimakompas.core.config import Source
from klimakompas.core.http import HttpClient

log = structlog.get_logger()


class ControlFailedError(Exception):
    """A data quality control failed, so the load is rolled back and old data stays."""


@dataclass
class RunContext:
    source: Source
    client: HttpClient
    data_dir: Path
    conn: Connection | None = None
    checks: list["Check"] = field(default_factory=list)

    @property
    def db(self) -> Connection:
        assert self.conn is not None
        return self.conn


class Check(BaseModel):
    check_id: str
    passed: bool
    value: float | None = None
    expected: float | None = None


class LoadResult(BaseModel):
    rows: int


class Connector(Protocol):
    source_id: str

    def fetch(self, ctx: RunContext) -> Any: ...

    def parse(self, artifacts: Any) -> Any: ...

    def load(self, frame: Any, ctx: RunContext) -> LoadResult: ...


def control(ctx: RunContext, check_id: str, value: float, expected: float, tol: float = 0) -> None:
    """Record a control; `tol` is a relative tolerance around `expected`."""
    passed = abs(value - expected) <= tol * abs(expected)
    ctx.checks.append(Check(check_id=check_id, passed=passed, value=value, expected=expected))
    log.info("control", source=ctx.source.id, check=check_id, value=value, expected=expected)


def record(ctx: RunContext, check_id: str, value: float) -> None:
    """Record an informative measure that has no expected value."""
    ctx.checks.append(Check(check_id=check_id, passed=True, value=value))
    log.info("measure", source=ctx.source.id, check=check_id, value=value)


def _write_checks(conn: Connection, ctx: RunContext, now: datetime) -> None:
    for check in ctx.checks:
        conn.execute(
            text(
                "INSERT INTO meta.dq_checks (source_id, check_id, status, value, details, "
                "checked_at) VALUES (:source, :check, :status, :value, "
                "jsonb_build_object('expected', CAST(:expected AS double precision)), :now) "
                "ON CONFLICT (source_id, check_id) DO UPDATE SET status = EXCLUDED.status, "
                "value = EXCLUDED.value, details = EXCLUDED.details, "
                "checked_at = EXCLUDED.checked_at"
            ),
            {
                "source": ctx.source.id,
                "check": check.check_id,
                "status": "pass" if check.passed else "fail",
                "value": check.value,
                "expected": check.expected,
                "now": now,
            },
        )


def run_connector(connector: Connector, ctx: RunContext, engine: Engine) -> LoadResult:
    """Fetch, parse and load in one transaction; on error the previous data stays in place."""
    source_id = connector.source_id
    started = datetime.now(UTC)
    with engine.begin() as conn:
        run_id = conn.execute(
            text(
                "INSERT INTO meta.etl_runs (source_id, started_at, status) "
                "VALUES (:source, :started, 'running') RETURNING run_id"
            ),
            {"source": source_id, "started": started},
        ).scalar_one()

    try:
        artifacts = connector.fetch(ctx)
        frame = connector.parse(artifacts)
        with engine.begin() as conn:
            ctx.conn = conn
            result = connector.load(frame, ctx)
            failed = [check.check_id for check in ctx.checks if not check.passed]
            if failed:
                raise ControlFailedError(f"failed controls: {', '.join(failed)}")
            now = datetime.now(UTC)
            _write_checks(conn, ctx, now)
            conn.execute(
                text(
                    "UPDATE meta.etl_runs SET finished_at = :now, status = 'success', "
                    "rows = :rows WHERE run_id = :run_id"
                ),
                {"now": now, "rows": result.rows, "run_id": run_id},
            )
            conn.execute(
                text(
                    "INSERT INTO meta.sources (source_id, last_success_at, last_status, "
                    "last_error, record_count) VALUES (:source, :now, 'success', NULL, :rows) "
                    "ON CONFLICT (source_id) DO UPDATE SET "
                    "last_success_at = EXCLUDED.last_success_at, last_status = 'success', "
                    "last_error = NULL, record_count = EXCLUDED.record_count"
                ),
                {"source": source_id, "now": now, "rows": result.rows},
            )
        return result
    except Exception as error:
        now = datetime.now(UTC)
        message = f"{type(error).__name__}: {error}"[:1000]
        with engine.begin() as conn:
            _write_checks(conn, ctx, now)
            conn.execute(
                text(
                    "UPDATE meta.etl_runs SET finished_at = :now, status = 'failed', "
                    "error = :error WHERE run_id = :run_id"
                ),
                {"now": now, "error": message, "run_id": run_id},
            )
            conn.execute(
                text(
                    "INSERT INTO meta.sources (source_id, last_status, last_error) "
                    "VALUES (:source, 'failed', :error) ON CONFLICT (source_id) DO UPDATE SET "
                    "last_status = 'failed', last_error = EXCLUDED.last_error"
                ),
                {"source": source_id, "error": message},
            )
        raise
