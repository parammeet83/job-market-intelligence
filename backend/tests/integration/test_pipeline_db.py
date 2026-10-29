"""Pipeline behaviour against a real PostgreSQL database (migrations applied, writer role)."""

from copy import deepcopy
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from backend.ingestion.orchestrator import run_pipeline
from backend.ingestion.reprocess import reprocess_skills
from backend.ingestion.skills.extractor import SkillDictionary, load_skill_dictionary
from backend.ops.roles import verify
from backend.tests.conftest import StaticJobicy, StaticRemoteOk, day, load_fixture

pytestmark = pytest.mark.integration


def jobicy_jobs(n: int = 30, start: int = 1000) -> list[dict[str, Any]]:
    """Synthetic Jobicy-shaped records (enough to exercise count baselines)."""
    base = load_fixture("jobicy_jobs.json")["jobs"][0]
    jobs = []
    for i in range(start, start + n):
        job = deepcopy(base)
        job.update(
            id=i,
            url=f"https://jobicy.com/jobs/{i}-data-analyst",
            jobTitle=f"Data Analyst {i}" if i % 3 else f"Data Engineer {i}",
        )
        jobs.append(job)
    return jobs


def remoteok_jobs(include_invalid: bool = False) -> list[dict[str, Any]]:
    """Fixture records: 2 in scope, 1 out of scope (+1 invalid record when requested)."""
    records = load_fixture("remoteok_api.json")[1:]
    return records if include_invalid else records[:3]


def run(
    engine: Engine | None,
    configs: dict[str, Any],
    *,
    jobicy: list[dict[str, Any]] | None,
    remoteok: list[dict[str, Any]] | None,
    n_day: int,
    dry_run: bool = False,
    jobicy_kwargs: dict[str, Any] | None = None,
    remoteok_fail: bool = False,
) -> Any:
    adapters: dict[str, Any] = {}
    selected = []
    if jobicy is not None:
        adapters["jobicy"] = StaticJobicy(
            configs["jobicy"], jobicy, fetched_at=day(n_day), **(jobicy_kwargs or {})
        )
        selected.append("jobicy")
    if remoteok is not None or remoteok_fail:
        adapters["remoteok"] = StaticRemoteOk(
            configs["remoteok"], remoteok or [], fetched_at=day(n_day), fail=remoteok_fail
        )
        selected.append("remoteok")
    return run_pipeline(
        engine=engine,
        trigger="test",
        dry_run=dry_run,
        source_ids=selected,
        configs=configs,
        adapters=adapters,
        now_fn=lambda: day(n_day),
    )


def scalar(engine: Engine, sql: str, **params: Any) -> Any:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def test_schema_and_views_exist(clean_db: Engine) -> None:
    tables = scalar(
        clean_db,
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'",
    )
    views = scalar(
        clean_db, "SELECT count(*) FROM information_schema.views WHERE table_schema='public'"
    )
    assert tables == 9  # 8 project tables + alembic_version
    assert views == 6


def test_end_to_end_and_idempotent(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    first = run(
        ingest_engine, source_configs, jobicy=jobicy_jobs(), remoteok=remoteok_jobs(), n_day=10
    )
    assert first.status == "succeeded"
    assert first.total("inserted") == 32 and first.total("updated") == 0
    assert first.sources["remoteok"].out_of_scope == 1
    second = run(
        ingest_engine, source_configs, jobicy=jobicy_jobs(), remoteok=remoteok_jobs(), n_day=10
    )
    assert second.total("inserted") == 0 and second.total("updated") == 32
    assert scalar(clean_db, "SELECT count(*) FROM jobs") == 32
    assert scalar(clean_db, "SELECT count(*) FROM job_observations") == 32
    links = scalar(clean_db, "SELECT count(*) FROM job_skills")
    assert links > 0
    third = run(
        ingest_engine, source_configs, jobicy=jobicy_jobs(), remoteok=remoteok_jobs(), n_day=10
    )
    assert scalar(clean_db, "SELECT count(*) FROM job_skills") == links
    assert third.status == "succeeded"
    # Run audit + quality rows were written for each run.
    assert scalar(clean_db, "SELECT count(*) FROM ingestion_runs WHERE status='succeeded'") == 3
    assert (
        scalar(
            clean_db,
            "SELECT count(*) FROM data_quality_results "
            "WHERE check_name='post_write_integrity' AND outcome='pass'",
        )
        == 3
    )


def test_new_day_adds_observations_and_keeps_history(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    run(ingest_engine, source_configs, jobicy=jobicy_jobs(), remoteok=None, n_day=10)
    run(ingest_engine, source_configs, jobicy=jobicy_jobs(), remoteok=None, n_day=11)
    assert scalar(clean_db, "SELECT count(*) FROM job_observations") == 60
    assert scalar(clean_db, "SELECT count(DISTINCT observation_date) FROM job_observations") == 2
    first_seen = scalar(clean_db, "SELECT min(first_seen_at)::date FROM jobs")
    last_seen = scalar(clean_db, "SELECT max(last_seen_at)::date FROM jobs")
    assert str(first_seen) == "2026-11-10" and str(last_seen) == "2026-11-11"


def test_partial_source_failure_keeps_other_source(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    summary = run(
        ingest_engine,
        source_configs,
        jobicy=jobicy_jobs(),
        remoteok=None,
        remoteok_fail=True,
        n_day=10,
    )
    assert summary.status == "partial"
    assert summary.sources["jobicy"].inserted == 30
    assert summary.sources["remoteok"].success is False
    err = scalar(clean_db, "SELECT last_error_summary FROM sources WHERE id='remoteok'")
    assert "ConnectTimeout" in err
    assert scalar(clean_db, "SELECT status FROM ingestion_runs") == "partial"


def test_failed_source_never_marks_jobs_missing(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    run(ingest_engine, source_configs, jobicy=None, remoteok=remoteok_jobs(), n_day=10)
    for d in (11, 12, 13):
        run(ingest_engine, source_configs, jobicy=None, remoteok=None, remoteok_fail=True, n_day=d)
    assert scalar(clean_db, "SELECT count(*) FROM jobs WHERE status <> 'active'") == 0
    assert scalar(clean_db, "SELECT max(consecutive_misses) FROM jobs") == 0


def test_incomplete_fetch_skips_absence_inference(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    run(ingest_engine, source_configs, jobicy=jobicy_jobs(30), remoteok=None, n_day=10)
    for d in (11, 12, 13):
        s = run(
            ingest_engine,
            source_configs,
            jobicy=jobicy_jobs(5),
            remoteok=None,
            n_day=d,
            jobicy_kwargs={"complete": False},
        )
        assert s.sources["jobicy"].lifecycle_applied is False
    assert scalar(clean_db, "SELECT count(*) FROM jobs WHERE status = 'unconfirmed'") == 0


def test_absence_after_complete_fetches_marks_unconfirmed(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    jobs = jobicy_jobs(30)
    run(ingest_engine, source_configs, jobicy=jobs, remoteok=None, n_day=10)
    remaining = jobs[2:]  # two listings disappear from the feed
    run(ingest_engine, source_configs, jobicy=remaining, remoteok=None, n_day=11)
    assert scalar(clean_db, "SELECT count(*) FROM jobs WHERE status='unconfirmed'") == 0
    s = run(ingest_engine, source_configs, jobicy=remaining, remoteok=None, n_day=12)
    assert s.sources["jobicy"].unconfirmed == 2
    assert scalar(clean_db, "SELECT count(*) FROM jobs WHERE status='unconfirmed'") == 2
    # History is kept: the missing listings still have their earlier observations.
    assert (
        scalar(
            clean_db,
            "SELECT count(*) FROM job_observations o JOIN jobs j ON j.id=o.job_id "
            "WHERE j.status='unconfirmed'",
        )
        == 2
    )
    # Reappearance restores 'active'.
    run(ingest_engine, source_configs, jobicy=jobs, remoteok=None, n_day=13)
    assert scalar(clean_db, "SELECT count(*) FROM jobs WHERE status='unconfirmed'") == 0


def test_status_api_closure_marks_expired(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    jobs = jobicy_jobs(30)
    run(ingest_engine, source_configs, jobicy=jobs, remoteok=None, n_day=10)
    s = run(
        ingest_engine,
        source_configs,
        jobicy=jobs[2:],
        remoteok=None,
        n_day=11,
        jobicy_kwargs={"status": {"1000": "closed", "1001": "active"}},
    )
    assert s.sources["jobicy"].status_checks == 2 and s.sources["jobicy"].expired == 1
    row = None
    with clean_db.connect() as conn:
        row = conn.execute(
            text(
                "SELECT status, source_reported_closed_at, consecutive_misses "
                "FROM jobs WHERE source_job_id='1000'"
            )
        ).one()
        verified = conn.execute(
            text("SELECT status, last_verified_active_at FROM jobs WHERE source_job_id='1001'")
        ).one()
        obs = conn.execute(
            text(
                "SELECT observation_method, observed_status FROM job_observations"
                " o JOIN jobs j ON j.id=o.job_id WHERE j.source_job_id='1000' "
                "AND observation_date='2026-11-11'"
            )
        ).one()
    assert row.status == "expired" and row.source_reported_closed_at is not None
    assert verified.status == "active" and verified.last_verified_active_at is not None
    assert tuple(obs) == ("status_check", "expired")


def test_empty_feed_never_triggers_absence(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    run(ingest_engine, source_configs, jobicy=jobicy_jobs(30), remoteok=None, n_day=10)
    for d in (11, 12, 13):
        s = run(ingest_engine, source_configs, jobicy=[], remoteok=None, n_day=d)
        assert s.sources["jobicy"].lifecycle_applied is False
    assert scalar(clean_db, "SELECT count(*) FROM jobs WHERE status <> 'active'") == 0


def test_count_anomaly_blocks_absence_inference(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    jobs = jobicy_jobs(40)
    for d in (10, 11, 12):
        run(ingest_engine, source_configs, jobicy=jobs, remoteok=None, n_day=d)
    s = run(ingest_engine, source_configs, jobicy=jobs[:5], remoteok=None, n_day=13)
    assert s.sources["jobicy"].anomaly is not None
    assert s.status == "partial"
    assert scalar(clean_db, "SELECT count(*) FROM jobs WHERE status <> 'active'") == 0


def test_dry_run_writes_nothing(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    run(ingest_engine, source_configs, jobicy=jobicy_jobs(10), remoteok=None, n_day=10)
    before = scalar(clean_db, "SELECT count(*) FROM ingestion_runs")
    s = run(
        ingest_engine, source_configs, jobicy=jobicy_jobs(15), remoteok=None, n_day=11, dry_run=True
    )
    assert s.run_id is None
    assert s.sources["jobicy"].would_update == 10 and s.sources["jobicy"].would_insert == 5
    assert scalar(clean_db, "SELECT count(*) FROM jobs") == 10
    assert scalar(clean_db, "SELECT count(*) FROM ingestion_runs") == before


def test_database_constraints(clean_db: Engine, ingest_engine: Engine, source_configs: Any) -> None:
    run(ingest_engine, source_configs, jobicy=jobicy_jobs(3), remoteok=None, n_day=10)
    bad_statements = [
        "UPDATE jobs SET salary_min = 200, salary_max = 100 WHERE id = 1",
        "UPDATE jobs SET salary_currency = 'usd' WHERE id = 1",
        "UPDATE jobs SET work_mode = 'moon' WHERE id = 1",
        "UPDATE jobs SET status = 'deleted' WHERE id = 1",
        "UPDATE jobs SET salary_min = 0 WHERE id = 1",
        "INSERT INTO job_observations (job_id, run_id, source_id, observation_date, observed_at,"
        " observation_method, observed_status) SELECT job_id, run_id, source_id,"
        " observation_date, observed_at, 'feed', 'active' FROM job_observations LIMIT 1",
        "INSERT INTO job_skills (job_id, skill_id, dictionary_version, matched_in)"
        " VALUES (999999, 1, 'x', '{}')",
    ]
    for sql in bad_statements:
        with pytest.raises(IntegrityError), clean_db.begin() as conn:
            conn.execute(text(sql))


def test_role_privileges(role_urls: dict[str, str], clean_db: Engine) -> None:
    results = verify(role_urls["api"], role_urls["ingest"])
    failed = [name for name, ok in results.items() if not ok]
    assert failed == []


def test_reprocess_skills_with_new_dictionary_version(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    run(ingest_engine, source_configs, jobicy=jobicy_jobs(3), remoteok=remoteok_jobs(), n_day=10)
    current = load_skill_dictionary()
    newer = SkillDictionary(
        version="2099.1.1", categories=current.categories, skills=current.skills
    )
    result = reprocess_skills(ingest_engine, day(10), newer)
    # Only Jobicy retains description text (retain_description_days > 0).
    assert result["jobs_reprocessed"] == 3
    assert scalar(clean_db, "SELECT count(DISTINCT dictionary_version) FROM job_skills") == 2
    assert (
        scalar(clean_db, "SELECT count(*) FROM jobs WHERE skills_dictionary_version = '2099.1.1'")
        == 3
    )
    assert (
        scalar(
            clean_db,
            "SELECT count(*) FROM job_descriptions d JOIN jobs j ON j.id = d.job_id"
            " WHERE j.source_id = 'remoteok'",
        )
        == 0
    )


def test_high_invalid_ratio_degrades_run(
    clean_db: Engine, ingest_engine: Engine, source_configs: Any
) -> None:
    s = run(ingest_engine, source_configs, jobicy=None, remoteok=remoteok_jobs(True), n_day=10)
    stats = s.sources["remoteok"]
    assert stats.invalid == 1 and stats.inserted == 2 and stats.quality_failed
    assert s.status == "partial"
    outcome = scalar(
        clean_db,
        "SELECT outcome FROM data_quality_results WHERE check_name = 'required_fields_and_formats'",
    )
    assert outcome == "fail"
    reasons = scalar(
        clean_db,
        "SELECT details->'reasons' FROM data_quality_results "
        "WHERE check_name = 'required_fields_and_formats'",
    )
    assert reasons == {"missing_source_id": 1}
