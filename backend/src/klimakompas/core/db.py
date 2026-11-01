"""Database access and bulk loading with COPY (SPEC §13)."""

from collections.abc import Iterable, Sequence
from functools import lru_cache
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, text

from klimakompas.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url.get_secret_value(), pool_pre_ping=True)


def stage_rows(
    conn: Connection,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    stage: str = "_stage",
) -> int:
    """COPY rows into a temporary table shaped like `table` and return the row count."""
    names = ", ".join(columns)
    conn.execute(text(f"DROP TABLE IF EXISTS {stage}"))
    conn.execute(
        text(
            f"CREATE TEMP TABLE {stage} ON COMMIT DROP AS SELECT {names} FROM {table} WITH NO DATA"
        )
    )
    count = 0
    cursor = conn.connection.driver_connection.cursor()  # type: ignore[union-attr]
    with cursor.copy(f"COPY {stage} ({names}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
            count += 1
    return count


def upsert_rows(
    conn: Connection,
    table: str,
    columns: Sequence[str],
    key: Sequence[str],
    rows: Iterable[Sequence[Any]],
) -> int:
    """Idempotent bulk upsert (SPEC §14)."""
    count = stage_rows(conn, table, columns, rows)
    names = ", ".join(columns)
    updates = ", ".join(f"{name} = EXCLUDED.{name}" for name in columns if name not in key)
    action = f"DO UPDATE SET {updates}" if updates else "DO NOTHING"
    conn.execute(
        text(
            f"INSERT INTO {table} ({names}) SELECT {names} FROM _stage "
            f"ON CONFLICT ({', '.join(key)}) {action}"
        )
    )
    return count
