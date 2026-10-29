"""Engine construction shared by the API (read-only role) and the pipeline (writer role)."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url


def normalize_database_url(url: str) -> str:
    """Accept provider-style URLs (postgres://, postgresql://) and force the psycopg 3 driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def database_name(url: str) -> str | None:
    return make_url(normalize_database_url(url)).database


def make_engine(url: str, *, pool_size: int = 2, max_overflow: int = 2) -> Engine:
    """Small pool + pre-ping: Neon computes scale to zero and serverless instances are reused.

    `prepare_threshold=None` disables server-side prepared statements so the engine also works
    through Neon's PgBouncer (transaction pooling) endpoint.
    """
    return create_engine(
        normalize_database_url(url),
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"prepare_threshold": None, "connect_timeout": 10},
    )
