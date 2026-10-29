"""Least-privilege PostgreSQL roles.

    uv run python -m backend.ops.roles provision --write-env .env
    uv run python -m backend.ops.roles verify

`provision` connects with MIGRATION_DATABASE_URL (owner role) and creates/updates:
  * jmp_api_ro  - public API. SELECT on analytics tables/views only, read-only transactions,
                  10 s statement timeout. No access to transient description text.
  * jmp_ingest  - pipeline. SELECT/INSERT/UPDATE on pipeline tables; DELETE only on the
                  derived tables job_skills and job_descriptions. It cannot delete jobs or
                  historical observations, run DDL or TRUNCATE.
Passwords are generated locally (or read from JMP_API_RO_PASSWORD / JMP_INGEST_PASSWORD),
are never printed, and with --write-env are written into the git-ignored .env file as
API_DATABASE_URL / INGEST_DATABASE_URL.

`verify` connects as each role and proves the privileges by attempting forbidden operations
inside transactions that are always rolled back.
"""

import argparse
import os
import secrets
import sys
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError

from backend.core.config import get_settings
from backend.core.db import normalize_database_url

API_ROLE = "jmp_api_ro"
INGEST_ROLE = "jmp_ingest"
READ_TABLES = [
    "sources",
    "jobs",
    "job_observations",
    "skills",
    "job_skills",
    "ingestion_runs",
    "data_quality_results",
    "v_jobs_public",
    "v_job_skills_current",
    "v_daily_listing_activity",
    "v_skill_share_active",
    "v_salary_disclosure",
    "v_source_health",
]
WRITE_TABLES = [
    "sources",
    "jobs",
    "job_observations",
    "skills",
    "ingestion_runs",
    "data_quality_results",
]
DERIVED_TABLES = ["job_skills", "job_descriptions"]


def _ident(conn: Connection, name: str) -> str:
    return str(conn.execute(text("SELECT quote_ident(:n)"), {"n": name}).scalar_one())


def _literal(conn: Connection, value: str) -> str:
    return str(conn.execute(text("SELECT quote_literal(:v)"), {"v": value}).scalar_one())


def provision(
    engine: Engine,
    api_password: str,
    ingest_password: str,
    api_role: str = API_ROLE,
    ingest_role: str = INGEST_ROLE,
) -> None:
    with engine.begin() as conn:
        db = _ident(conn, conn.execute(text("SELECT current_database()")).scalar_one())
        for role, password in ((api_role, api_password), (ingest_role, ingest_password)):
            r, pw = _ident(conn, role), _literal(conn, password)
            exists = conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}
            ).scalar()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(
                text(
                    f"{verb} ROLE {r} WITH LOGIN PASSWORD {pw} NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT"
                )
            )
            conn.execute(text(f"GRANT CONNECT ON DATABASE {db} TO {r}"))
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {r}"))
            conn.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {r}"))
        api, ingest = _ident(conn, api_role), _ident(conn, ingest_role)
        conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        conn.execute(text(f"GRANT SELECT ON {', '.join(READ_TABLES)} TO {api}"))
        conn.execute(text(f"ALTER ROLE {api} SET default_transaction_read_only = on"))
        conn.execute(text(f"ALTER ROLE {api} SET statement_timeout = '10s'"))
        conn.execute(text(f"GRANT SELECT, INSERT, UPDATE ON {', '.join(WRITE_TABLES)} TO {ingest}"))
        conn.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(DERIVED_TABLES)} TO {ingest}")
        )
        conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ingest}"))
        conn.execute(text(f"ALTER ROLE {ingest} SET statement_timeout = '120s'"))


def _attempt(conn: Connection, sql: str) -> bool:
    """True if the statement was REJECTED (what we want for forbidden operations)."""
    savepoint = conn.begin_nested()
    try:
        conn.execute(text(sql))
    except DBAPIError:
        savepoint.rollback()
        return True
    savepoint.rollback()
    return False


def verify(api_url: str, ingest_url: str) -> dict[str, bool]:
    """Each check is True when the role behaves as required."""
    checks: dict[str, bool] = {}
    api_engine = create_engine(
        normalize_database_url(api_url), connect_args={"prepare_threshold": None}
    )
    with api_engine.connect() as conn:
        tx = conn.begin()
        checks["api_can_select_jobs"] = not _attempt(conn, "SELECT count(*) FROM jobs")
        checks["api_can_select_views"] = not _attempt(conn, "SELECT count(*) FROM v_jobs_public")
        checks["api_insert_denied"] = _attempt(
            conn,
            "INSERT INTO ingestion_runs (trigger, skills_dictionary_version) VALUES ('test', 'x')",
        )
        checks["api_update_denied"] = _attempt(conn, "UPDATE jobs SET status = status")
        checks["api_delete_denied"] = _attempt(conn, "DELETE FROM job_observations")
        checks["api_ddl_denied"] = _attempt(conn, "CREATE TABLE jmp_probe (id int)")
        checks["api_descriptions_denied"] = _attempt(conn, "SELECT 1 FROM job_descriptions")
        checks["api_session_read_only"] = (
            conn.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        )
        tx.rollback()
    with api_engine.connect() as conn:
        # Even if a client overrides the read-only default, the grants must still refuse writes.
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE"))
        conn.commit()
        tx = conn.begin()
        checks["api_insert_denied_by_grants"] = _attempt(
            conn,
            "INSERT INTO ingestion_runs (trigger, skills_dictionary_version) VALUES ('test', 'x')",
        )
        checks["api_update_denied_by_grants"] = _attempt(conn, "UPDATE jobs SET status = status")
        tx.rollback()
    api_engine.dispose()
    ingest_engine = create_engine(
        normalize_database_url(ingest_url), connect_args={"prepare_threshold": None}
    )
    with ingest_engine.connect() as conn:
        tx = conn.begin()
        checks["ingest_can_update_jobs"] = not _attempt(conn, "UPDATE jobs SET status = status")
        checks["ingest_delete_jobs_denied"] = _attempt(conn, "DELETE FROM jobs")
        checks["ingest_delete_observations_denied"] = _attempt(conn, "DELETE FROM job_observations")
        checks["ingest_truncate_denied"] = _attempt(conn, "TRUNCATE job_observations")
        checks["ingest_ddl_denied"] = _attempt(conn, "CREATE TABLE jmp_probe (id int)")
        checks["ingest_drop_denied"] = _attempt(conn, "DROP TABLE jobs")
        tx.rollback()
    ingest_engine.dispose()
    return checks


def _role_url(base: URL, role: str, password: str, pooled: bool) -> str:
    host = base.host or ""
    if pooled and host.endswith(".neon.tech") and "-pooler" not in host.split(".")[0]:
        first, rest = host.split(".", 1)
        host = f"{first}-pooler.{rest}"
    return base.set(username=role, password=password, host=host).render_as_string(
        hide_password=False
    )


def _write_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    keys = set(updates)
    kept = [ln for ln in lines if ln.split("=", 1)[0].strip() not in keys]
    kept += [f"{k}={v}" for k, v in updates.items()]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backend.ops.roles")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("provision")
    p.add_argument("--write-env", type=Path, help="write role URLs into this (git-ignored) file")
    sub.add_parser("verify")
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.cmd == "provision":
        if not settings.migration_database_url:
            print("MIGRATION_DATABASE_URL is not set.", file=sys.stderr)
            return 2
        api_pw = os.environ.get("JMP_API_RO_PASSWORD") or secrets.token_urlsafe(32)
        ingest_pw = os.environ.get("JMP_INGEST_PASSWORD") or secrets.token_urlsafe(32)
        engine = create_engine(
            normalize_database_url(settings.migration_database_url),
            connect_args={"prepare_threshold": None},
        )
        provision(engine, api_pw, ingest_pw)
        print(f"Provisioned roles {API_ROLE} and {INGEST_ROLE} (passwords not shown).")
        if args.write_env:
            base = make_url(normalize_database_url(settings.migration_database_url))
            _write_env(
                args.write_env,
                {
                    "API_DATABASE_URL": _role_url(base, API_ROLE, api_pw, pooled=True),
                    "INGEST_DATABASE_URL": _role_url(base, INGEST_ROLE, ingest_pw, pooled=True),
                },
            )
            print(f"Wrote API_DATABASE_URL and INGEST_DATABASE_URL to {args.write_env}.")
        return 0

    if not (settings.api_database_url and settings.ingest_database_url):
        print("API_DATABASE_URL and INGEST_DATABASE_URL must be set.", file=sys.stderr)
        return 2
    results = verify(settings.api_database_url, settings.ingest_database_url)
    for name, ok in results.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
