import argparse
import os
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from backend.core.db import normalize_database_url
from backend.ops.roles import provision
from backend.tests.conftest import get_test_database_url

ROOT = Path(__file__).resolve().parents[3]
API_ROLE, INGEST_ROLE = "jmp_test_api_ro", "jmp_test_ingest"
DATA_TABLES = [
    "data_quality_results",
    "job_skills",
    "job_descriptions",
    "job_observations",
    "jobs",
    "ingestion_runs",
    "skills",
    "sources",
]


def _alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.cmd_opts = argparse.Namespace(x=[f"url={url}"])
    return cfg


@pytest.fixture(scope="session")
def database_url() -> str:
    url = get_test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; integration tests skipped")
    name = make_url(normalize_database_url(url)).database or ""
    if "test" not in name:
        pytest.exit(f"Refusing to run destructive tests against database {name!r}", 2)
    return normalize_database_url(url)


@pytest.fixture(scope="session")
def admin_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url, connect_args={"prepare_threshold": None})
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    os.environ["EXPECTED_DATABASE_NAME"] = make_url(database_url).database or ""
    command.upgrade(_alembic_config(database_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def role_urls(admin_engine: Engine, database_url: str) -> dict[str, str]:
    api_pw, ingest_pw = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    provision(admin_engine, api_pw, ingest_pw, api_role=API_ROLE, ingest_role=INGEST_ROLE)
    base = make_url(database_url)
    return {
        "api": base.set(username=API_ROLE, password=api_pw).render_as_string(hide_password=False),
        "ingest": base.set(username=INGEST_ROLE, password=ingest_pw).render_as_string(
            hide_password=False
        ),
    }


@pytest.fixture(scope="session")
def ingest_engine(role_urls: dict[str, str]) -> Iterator[Engine]:
    engine = create_engine(role_urls["ingest"], connect_args={"prepare_threshold": None})
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def api_engine(role_urls: dict[str, str]) -> Iterator[Engine]:
    engine = create_engine(role_urls["api"], connect_args={"prepare_threshold": None})
    yield engine
    engine.dispose()


@pytest.fixture
def clean_db(admin_engine: Engine) -> Engine:
    with admin_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(DATA_TABLES)} RESTART IDENTITY CASCADE"))
    return admin_engine
