"""Alembic environment: uses the repo's single engine and models (no URL in alembic.ini)."""
from logging.config import fileConfig

from alembic import context

from backend.app.db.models import Base
from backend.app.db.session import get_engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline (--sql) mode is not used in this project; run against a database.")
run_migrations_online()
