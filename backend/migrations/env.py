"""Alembic environment: all DDL is explicit SQL, so there is no target metadata."""

from alembic import context
from sqlalchemy import create_engine

from klimakompas.core.config import get_settings

url = (
    context.config.attributes.get("database_url") or get_settings().database_url.get_secret_value()
)
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
