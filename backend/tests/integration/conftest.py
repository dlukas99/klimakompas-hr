"""Integration tests run against the `db-test` PostGIS service and skip when it is not running."""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import OperationalError

from klimakompas.core.config import ROOT

DEFAULT_URL = (
    "postgresql+psycopg://kk_test:kk_test"  # pragma: allowlist secret
    "@localhost:5433/klimakompas_test"
)
SCHEMAS = ("tiles", "ml", "idx", "live", "haz", "pop", "meta", "ref")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_URL)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            for schema in SCHEMAS:
                conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS public.alembic_version"))
    except OperationalError:
        pytest.skip("db-test is not running (make test-db)")
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def conn(engine: Engine) -> Iterator[Connection]:
    """A connection whose changes are rolled back after the test."""
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()
