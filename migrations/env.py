"""Alembic environment with safety checks.

* URL comes from MIGRATION_DATABASE_URL, or `alembic -x url=...` (used by tests).
* If EXPECTED_DATABASE_NAME is set, the connected database name must match it exactly.
* With APP_ENV=production, EXPECTED_DATABASE_NAME is mandatory.
* Migrations run in a single transaction and never drop data automatically.
"""

import os
import sys

from alembic import context
from sqlalchemy import create_engine, pool, text

from backend.app.models import metadata
from backend.core.config import get_settings
from backend.core.db import normalize_database_url

config = context.config
target_metadata = metadata


def _resolve_url() -> str:
    url = context.get_x_argument(as_dictionary=True).get("url")
    url = url or get_settings().migration_database_url
    if not url:
        sys.exit("MIGRATION_DATABASE_URL is not set; refusing to guess a database.")
    return normalize_database_url(url)


def _verify_target(connection) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    expected = os.environ.get("EXPECTED_DATABASE_NAME") or settings.expected_database_name
    actual = connection.execute(text("SELECT current_database()")).scalar_one()
    if settings.app_env == "production" and not expected:
        sys.exit("APP_ENV=production requires EXPECTED_DATABASE_NAME for migrations.")
    if expected and actual != expected:
        sys.exit(f"Connected to database {actual!r}, expected {expected!r}. Aborting.")


def run_migrations_offline() -> None:
    context.configure(url=_resolve_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        _resolve_url(), poolclass=pool.NullPool, connect_args={"prepare_threshold": None}
    )
    with engine.connect() as connection:
        _verify_target(connection)
        # The verification query autobegins a transaction; end it so Alembic owns the
        # migration transaction (otherwise nothing would be committed).
        connection.commit()
        context.configure(
            connection=connection, target_metadata=target_metadata, transaction_per_migration=False
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
