"""Read-only database access for the API.

Every request runs inside a transaction that is explicitly READ ONLY with a statement timeout,
on top of the read-only role (jmp_api_ro) whose grants already forbid writes.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Connection, Engine, text

from backend.core.config import get_settings
from backend.core.db import make_engine

STATEMENT_TIMEOUT = "8s"


class DatabaseNotConfigured(RuntimeError):
    pass


@lru_cache
def get_engine() -> Engine:
    url = get_settings().api_database_url
    if not url:
        raise DatabaseNotConfigured("API_DATABASE_URL is not set")
    return make_engine(url, pool_size=3, max_overflow=2)


def get_connection() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        try:
            yield conn
        finally:
            conn.rollback()
