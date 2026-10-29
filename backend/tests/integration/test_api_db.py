"""API endpoints against a real database through the read-only role."""

import csv
import io
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from backend.app import main
from backend.app.database import get_connection
from backend.tests.conftest import StaticJobicy, StaticRemoteOk, day, load_fixture
from backend.tests.integration.test_pipeline_db import jobicy_jobs

pytestmark = pytest.mark.integration
PERIOD = "start=2026-11-01&end=2026-11-30"


@pytest.fixture
def seeded(clean_db: Engine, ingest_engine: Engine, source_configs: Any) -> Engine:
    from backend.ingestion.orchestrator import run_pipeline

    jobs = jobicy_jobs(20) + load_fixture("jobicy_jobs.json")["jobs"]
    for n_day in (10, 11):
        adapters = {
            "jobicy": StaticJobicy(source_configs["jobicy"], jobs, fetched_at=day(n_day)),
            "remoteok": StaticRemoteOk(
                source_configs["remoteok"],
                load_fixture("remoteok_api.json")[1:4],
                fetched_at=day(n_day),
            ),
        }
        run_pipeline(
            engine=ingest_engine,
            trigger="test",
            configs=source_configs,
            adapters=adapters,
            now_fn=lambda d=n_day: day(d),
        )
    return clean_db


@pytest.fixture
def client(api_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    def connection() -> Iterator[Any]:
        with api_engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            yield conn
            conn.rollback()

    main.app.dependency_overrides[get_connection] = connection
    monkeypatch.setattr(main, "get_engine", lambda: api_engine)
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def scalar(engine: Engine, sql: str) -> Any:
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar_one()


def test_health_reports_database(client: TestClient, seeded: Engine) -> None:
    body = client.get("/api/v1/health").json()
    assert body == {"status": "ok", "database": "ok", "version": main.VERSION}


def test_summary_matches_database(client: TestClient, seeded: Engine) -> None:
    body = client.get(f"/api/v1/summary?{PERIOD}").json()
    assert body["jobs_total"] == scalar(seeded, "SELECT count(*) FROM jobs")
    assert body["jobs_active"] == scalar(seeded, "SELECT count(*) FROM jobs WHERE status='active'")
    assert body["observations_total"] == scalar(seeded, "SELECT count(*) FROM job_observations")
    assert body["listings_in_period"] == body["jobs_total"]
    assert body["new_in_period"] == body["jobs_total"]
    assert body["latest_run"]["status"] == "succeeded"
    assert body["sources_enabled"] == 2


def test_skill_share_uses_distinct_listing_denominator(client: TestClient, seeded: Engine) -> None:
    body = client.get(f"/api/v1/skills?{PERIOD}").json()
    eligible = scalar(seeded, "SELECT count(*) FROM jobs")
    assert body["eligible_listings"] == eligible  # not the 2x observation rows
    sql = next(i for i in body["items"] if i["slug"] == "sql")
    expected = scalar(
        seeded, "SELECT count(DISTINCT job_id) FROM v_job_skills_current WHERE skill_slug='sql'"
    )
    assert sql["listings"] == expected
    assert sql["share_pct"] == round(100 * expected / eligible, 2)
    # Skills absent from the data are listed with an explicit zero, not omitted or invented.
    tableau = next(i for i in body["items"] if i["slug"] == "tableau")
    assert tableau["listings"] == 0
    assert body["small_sample"] is True


def test_skill_trends(client: TestClient, seeded: Engine) -> None:
    body = client.get(f"/api/v1/skills/trends?{PERIOD}&skill=sql&skill=python").json()
    days = {p["period"] for p in body["points"]}
    assert days == {"2026-11-10", "2026-11-11"}
    assert all(
        p["eligible_listings"] == scalar(seeded, "SELECT count(*) FROM jobs")
        for p in body["points"]
    )
    assert client.get(f"/api/v1/skills/trends?{PERIOD}&skill=DROP%20TABLE").status_code == 422


def test_jobs_filters_and_pagination(client: TestClient, seeded: Engine) -> None:
    page = client.get("/api/v1/jobs?page_size=5&page=2").json()
    assert page["page"] == 2 and len(page["items"]) == 5
    assert page["total"] == scalar(seeded, "SELECT count(*) FROM jobs WHERE status='active'")
    analysts = client.get("/api/v1/jobs?role=Data%20Analyst&page_size=100").json()
    assert analysts["total"] > 0
    assert all(i["role_category"] == "Data Analyst" for i in analysts["items"])
    with_sql = client.get("/api/v1/jobs?skill=sql&page_size=100").json()
    assert all(any(s["slug"] == "sql" for s in i["skills"]) for i in with_sql["items"])
    searched = client.get("/api/v1/jobs?q=Example%20GmbH").json()
    assert searched["total"] == 1
    wildcard = client.get("/api/v1/jobs?q=%25").json()
    assert wildcard["total"] == 0  # % is escaped, not a wildcard
    salary = client.get("/api/v1/jobs?salary_disclosed=false&page_size=100").json()
    assert all(i["salary_text"] is None and i["salary_min"] is None for i in salary["items"])
    sorted_titles = client.get("/api/v1/jobs?sort=title_asc&page_size=100").json()["items"]
    titles = [i["title_normalized"] for i in sorted_titles]
    assert titles == sorted(titles)


def test_job_detail_and_history(client: TestClient, seeded: Engine) -> None:
    job_id = scalar(seeded, "SELECT id FROM jobs WHERE source_job_id='900001'")
    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["url"].startswith("https://jobicy.com/")
    assert len(body["observations"]) == 2
    assert "Jobicy" in body["attribution"]
    assert client.get("/api/v1/jobs/0").status_code == 422
    assert client.get("/api/v1/jobs/99999999").status_code == 404


def test_salaries_never_mix_currencies(client: TestClient, seeded: Engine) -> None:
    body = client.get(f"/api/v1/analytics/salaries?{PERIOD}").json()
    groups = {(g["currency"], g["period"]) for g in body["groups"]}
    assert ("USD", "year") in groups and ("EUR", "year") in groups
    assert all(g["currency"] and g["period"] for g in body["groups"])
    d = body["disclosure"]
    assert d["with_unit_unknown"] == 1  # Remote OK amount without currency/period
    assert d["with_comparable_salary"] <= d["with_salary_info"] <= d["listings"]


def test_roles_locations_lifecycle_sources_runs(client: TestClient, seeded: Engine) -> None:
    roles = client.get(f"/api/v1/analytics/roles?{PERIOD}").json()
    assert sum(r["listings"] for r in roles["roles"]) == roles["population"]
    locs = client.get(f"/api/v1/analytics/locations?{PERIOD}").json()
    assert sum(c["listings"] for c in locs["countries"]) == locs["population"]
    life = client.get(f"/api/v1/analytics/lifecycle?{PERIOD}").json()
    assert life["statuses"][0]["status"] == "active"
    sources = client.get("/api/v1/sources").json()
    by_id = {s["source_id"]: s for s in sources}
    assert by_id["jobicy"]["health"] in ("healthy", "degraded")
    assert by_id["arbeitnow"]["enabled"] is False and by_id["arbeitnow"]["disabled_reason"]
    runs = client.get("/api/v1/ingestion-runs").json()
    assert len(runs) == 2 and runs[0]["quality_failures"] == 0
    dq = client.get("/api/v1/data-quality").json()
    assert {q["check_name"] for q in dq} >= {"fetch_completeness", "post_write_integrity"}
    filters = client.get("/api/v1/meta/filters").json()
    assert {s["label"] for s in filters["sources"]} == {"jobicy", "remoteok"}


def test_csv_exports_respect_source_permissions(client: TestClient, seeded: Engine) -> None:
    resp = client.get("/api/v1/exports/jobs.csv?status=all")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert rows and {r["source_name"] for r in rows} == {"Jobicy"}
    assert "description" not in rows[0]
    skills = list(
        csv.DictReader(io.StringIO(client.get(f"/api/v1/exports/skills.csv?{PERIOD}").text))
    )
    assert any(r["slug"] == "python" for r in skills)
    obs = list(
        csv.DictReader(io.StringIO(client.get(f"/api/v1/exports/observations.csv?{PERIOD}").text))
    )
    assert obs and {r["source_id"] for r in obs} == {"jobicy"}


def test_api_cannot_modify_data(client: TestClient, seeded: Engine) -> None:
    before = scalar(seeded, "SELECT count(*) FROM jobs")
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/v1/jobs").status_code == 405
    assert scalar(seeded, "SELECT count(*) FROM jobs") == before


def test_empty_database_is_handled(client: TestClient, clean_db: Engine) -> None:
    summary = client.get("/api/v1/summary").json()
    assert summary["jobs_total"] == 0 and summary["freshness"] == "no_data"
    assert summary["latest_run"] is None and summary["salary_disclosure_pct"] is None
    skills = client.get("/api/v1/skills").json()
    assert skills["eligible_listings"] == 0
    assert client.get("/api/v1/jobs").json()["total"] == 0
