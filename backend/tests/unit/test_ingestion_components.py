from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import requests

from backend.core.logging import redact, safe_error_summary
from backend.ingestion.http import DisallowedHostError, HttpClient, SourceFetchError
from backend.ingestion.orchestrator import SourceStats, _overall_status, prepare_records
from backend.ingestion.skills.extractor import load_skill_dictionary
from backend.ingestion.sources.base import FetchResult, ParseError
from backend.ingestion.sources.jobicy import JobicyAdapter
from backend.ingestion.sources.remoteok import RemoteOkAdapter
from backend.ingestion.transformations.normalize import InvalidRecord, normalize_job
from backend.ingestion.transformations.roles import load_role_rules
from backend.ingestion.validation.batch import count_anomaly, validate_batch
from backend.tests.conftest import FakeClient, load_fixture

NOW = datetime(2026, 10, 29, 6, 0, tzinfo=UTC)


# --- HTTP client --------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status: int, payload: Any = None, headers: dict[str, str] | None = None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession(requests.Session):
    def __init__(self, responses: list[Any]) -> None:
        super().__init__()
        self.queue = list(responses)
        self.urls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> Any:  # type: ignore[override]
        self.urls.append(url)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def client(responses: list[Any], **kw: Any) -> tuple[HttpClient, list[float]]:
    sleeps: list[float] = []
    c = HttpClient(
        ["api.example.com"],
        session=FakeSession(responses),
        sleep=sleeps.append,
        min_interval=0,
        **kw,
    )
    return c, sleeps


def test_http_success_and_request_count() -> None:
    c, _ = client([FakeResponse(200, {"ok": 1})])
    assert c.get_json("https://api.example.com/x") == {"ok": 1}
    assert c.request_count == 1


def test_http_rejects_unlisted_host_and_plain_http() -> None:
    c, _ = client([])
    with pytest.raises(DisallowedHostError):
        c.get_json("https://evil.example.com/x")
    with pytest.raises(DisallowedHostError):
        c.get_json("http://api.example.com/x")
    with pytest.raises(DisallowedHostError):
        c.get_json("https://api.example.com.evil.com/x")


def test_http_retries_then_succeeds_with_backoff() -> None:
    c, sleeps = client([FakeResponse(503), requests.ConnectionError(), FakeResponse(200, [1])])
    assert c.get_json("https://api.example.com/x") == [1]
    assert sleeps == [2.0, 4.0]
    assert c.request_count == 3


def test_http_honours_retry_after() -> None:
    c, sleeps = client([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, {})])
    c.get_json("https://api.example.com/x")
    assert sleeps == [7.0]


def test_http_gives_up_on_excessive_retry_after() -> None:
    c, sleeps = client([FakeResponse(429, headers={"Retry-After": "3600"})])
    with pytest.raises(SourceFetchError, match="too long"):
        c.get_json("https://api.example.com/x")
    assert sleeps == []


def test_http_bounded_attempts() -> None:
    c, _ = client([FakeResponse(500)] * 3)
    with pytest.raises(SourceFetchError, match="after 3 attempts"):
        c.get_json("https://api.example.com/x")
    assert c.request_count == 3


def test_http_does_not_retry_client_errors() -> None:
    c, _ = client([FakeResponse(403)])
    with pytest.raises(SourceFetchError, match="HTTP 403"):
        c.get_json("https://api.example.com/x")
    assert c.request_count == 1


def test_http_redirect_to_other_host_is_refused() -> None:
    c, _ = client([FakeResponse(301, headers={"Location": "https://evil.example.com/"})])
    with pytest.raises(DisallowedHostError):
        c.get_json("https://api.example.com/x")


def test_http_invalid_json() -> None:
    c, _ = client([FakeResponse(200, ValueError("bad"))])
    with pytest.raises(SourceFetchError, match="not valid JSON"):
        c.get_json("https://api.example.com/x")


def test_http_enforces_min_interval() -> None:
    sleeps: list[float] = []
    clock = iter([0.0, 0.5, 0.5])  # 1st request stamp, 2nd throttle check, 2nd stamp
    c = HttpClient(
        ["api.example.com"],
        session=FakeSession([FakeResponse(200, 1)] * 2),
        sleep=sleeps.append,
        clock=lambda: next(clock),
        min_interval=2.0,
    )
    c.get_json("https://api.example.com/a")
    c.get_json("https://api.example.com/b")
    assert sleeps == [1.5]


# --- adapters -----------------------------------------------------------------------------


def test_jobicy_fetch_paginates_and_reports_incomplete(source_configs: Any) -> None:
    cfg = source_configs["jobicy"]
    pages = {
        "data-science": [
            {"jobs": [{"id": 1}], "hasMore": True, "nextCursor": "c1"},
            {"jobs": [{"id": 2}], "hasMore": False},
        ],
        "engineering": SourceFetchError("HTTP 503"),
        "admin": [{"jobs": [{"id": 3}], "hasMore": False}],
    }

    def respond(params: dict[str, Any]) -> Any:
        value = pages[params["industry"]]
        if isinstance(value, Exception):
            raise value
        return value.pop(0)

    fake = FakeClient({cfg.api_url: respond})
    result = JobicyAdapter(cfg, client=fake).fetch()  # type: ignore[arg-type]
    assert [r["id"] for r in result.records] == [1, 2, 3]
    assert result.complete is False
    assert any("engineering" in e for e in result.errors)
    assert fake.calls[1][1] == {"count": 200, "industry": "data-science", "cursor": "c1"}


def test_jobicy_fetch_raises_when_nothing_fetched(source_configs: Any) -> None:
    cfg = source_configs["jobicy"]
    fake = FakeClient({cfg.api_url: SourceFetchError("HTTP 500")})
    with pytest.raises(SourceFetchError):
        JobicyAdapter(cfg, client=fake).fetch()  # type: ignore[arg-type]


def test_jobicy_parse_fixture(source_configs: Any) -> None:
    adapter = JobicyAdapter(source_configs["jobicy"], client=FakeClient())  # type: ignore[arg-type]
    job = adapter.parse(load_fixture("jobicy_jobs.json")["jobs"][0])
    assert job.source_job_id == "900001"
    assert job.salary_currency == "USD" and job.salary_period == "yearly"
    assert job.employment_type_raw == "Full-Time" and job.level_raw == "Senior"
    assert job.published_at == datetime(2026, 10, 27, 10, tzinfo=UTC)
    with pytest.raises(ParseError):
        adapter.parse({"jobTitle": "x"})


def test_jobicy_status_check_batches(source_configs: Any) -> None:
    cfg = source_configs["jobicy"]
    status_url = cfg.options["status_url"]

    def respond(params: dict[str, Any]) -> Any:
        ids = params["ids"].split(",")
        return {"jobs": [{"id": int(i), "status": "closed" if i == "5" else "active"} for i in ids]}

    fake = FakeClient({status_url: respond})
    adapter = JobicyAdapter(cfg, client=fake)  # type: ignore[arg-type]
    result = adapter.check_status([str(i) for i in range(1, 151)] + ["abc"])
    assert len(fake.calls) == 2
    assert result["5"] == "closed" and result["150"] == "active" and "abc" not in result


def test_remoteok_fetch_skips_legal_notice_and_parses(source_configs: Any) -> None:
    cfg = source_configs["remoteok"]
    fake = FakeClient({cfg.api_url: load_fixture("remoteok_api.json")})
    adapter = RemoteOkAdapter(cfg, client=fake)  # type: ignore[arg-type]
    result = adapter.fetch()
    assert len(result.records) == 4 and result.complete
    first = adapter.parse(result.records[0])
    assert first.salary_min == 100000 and first.salary_currency is None
    assert first.salary_note and "not stated" in (first.salary_text or "")
    zero = adapter.parse(result.records[1])
    assert zero.salary_min is None and zero.salary_text is None
    with pytest.raises(ParseError):
        adapter.parse(result.records[3])


def test_remoteok_rejects_unexpected_payload(source_configs: Any) -> None:
    cfg = source_configs["remoteok"]
    fake = FakeClient({cfg.api_url: {"error": "x"}})
    with pytest.raises(SourceFetchError):
        RemoteOkAdapter(cfg, client=fake).fetch()  # type: ignore[arg-type]


# --- normalization + validation -----------------------------------------------------------


def _prepare(
    source_configs: Any, source: str, records: list[dict[str, Any]]
) -> tuple[list[Any], SourceStats]:
    cfg = source_configs[source]
    adapter_cls = JobicyAdapter if source == "jobicy" else RemoteOkAdapter
    adapter = adapter_cls(cfg, client=FakeClient())  # type: ignore[arg-type]
    stats = SourceStats(source_id=source)
    recs = prepare_records(
        adapter,
        FetchResult(records, True, NOW),
        stats=stats,
        skills=load_skill_dictionary(),
        roles=load_role_rules(),
    )
    return recs, stats


def test_prepare_jobicy_fixture(source_configs: Any) -> None:
    recs, stats = _prepare(source_configs, "jobicy", load_fixture("jobicy_jobs.json")["jobs"])
    by_id = {r.source_job_id: r for r in recs}
    # 900003 keeps the listing but drops its inconsistent salary; 900004 has a foreign URL host.
    assert set(by_id) == {"900001", "900002", "900003"}
    assert stats.invalid == 1 and stats.valid == 3
    analyst = by_id["900001"]
    assert analyst.title_normalized == "Senior Data Analyst"
    assert analyst.role_category == "Data Analyst"
    assert analyst.country == "United States"
    assert analyst.work_mode == "remote" and analyst.work_mode_basis == "source_default"
    assert analyst.salary_min == Decimal(90000) and analyst.salary_period == "year"
    assert analyst.employment_type == "full_time" and analyst.seniority == "senior"
    assert {"sql", "python", "power-bi"} <= set(analyst.skills)
    assert "excel" not in analyst.skills  # "Excel at stakeholder communication"
    engineer = by_id["900002"]
    assert "r" not in engineer.skills  # "R&D"
    assert engineer.country is None and engineer.location_original == "Europe"


def test_inconsistent_salary_keeps_listing_without_numbers(source_configs: Any) -> None:
    rec = dict(load_fixture("jobicy_jobs.json")["jobs"][2])
    recs, stats = _prepare(source_configs, "jobicy", [rec])
    assert len(recs) == 1 and stats.invalid == 0
    ml = recs[0]
    assert ml.salary_min is None and ml.salary_max is None and ml.salary_text
    assert stats.salary_issues == {"min_greater_than_max": 1}
    # Work mode uses title/location wording only; description text is not used.
    assert ml.work_mode == "remote" and ml.work_mode_basis == "source_default"
    assert ml.canonical_url == "https://jobicy.com/jobs/900003-ml-engineer"


def test_wrong_host_and_missing_fields_are_invalid_with_reasons(source_configs: Any) -> None:
    jobs = load_fixture("jobicy_jobs.json")["jobs"]
    broken = [
        jobs[3],
        {"id": 5, "url": "https://jobicy.com/jobs/5", "jobTitle": ""},
        {"id": 6, "jobTitle": "Data Analyst"},
    ]
    recs, stats = _prepare(source_configs, "jobicy", broken)
    assert recs == [] and stats.invalid == 3
    reasons = " ".join(stats.invalid_reasons)
    assert "host" in reasons and "missing_title" in reasons and "missing_url" in reasons


def test_duplicates_are_counted_and_first_kept(source_configs: Any) -> None:
    job = load_fixture("jobicy_jobs.json")["jobs"][0]
    twin = dict(job, jobTitle="Data Analyst (duplicate copy)")
    recs, stats = _prepare(source_configs, "jobicy", [job, twin])
    assert len(recs) == 1 and stats.duplicates == 1
    assert recs[0].title_original.startswith("Sr. Data Analyst")


def test_remoteok_scope_filter(source_configs: Any) -> None:
    records = load_fixture("remoteok_api.json")[1:]
    recs, stats = _prepare(source_configs, "remoteok", records)
    assert {r.source_job_id for r in recs} == {"800001", "800003"}
    assert stats.out_of_scope == 1 and stats.invalid == 1
    ae = next(r for r in recs if r.source_job_id == "800001")
    assert ae.canonical_url.startswith("https://remoteok.com/")
    assert ae.city == "Seattle" and ae.country == "United States"
    assert ae.salary_currency is None and ae.salary_min == Decimal(100000)
    assert {"dbt", "snowflake", "sql", "git"} <= set(ae.skills)


def test_future_publication_date_is_invalid(source_configs: Any) -> None:
    job = dict(load_fixture("jobicy_jobs.json")["jobs"][0])
    job["pubDate"] = (NOW + timedelta(days=30)).isoformat()
    _, stats = _prepare(source_configs, "jobicy", [job])
    assert stats.invalid == 1 and "future" in " ".join(stats.invalid_reasons)


def test_normalize_requires_title(source_configs: Any) -> None:
    from backend.ingestion.sources.base import ParsedJob

    with pytest.raises(InvalidRecord, match="missing_title"):
        normalize_job(
            ParsedJob(
                source_job_id="1",
                url="https://jobicy.com/x",
                title=" ",
                company=None,
                location=None,
            ),
            source=source_configs["jobicy"],
            observed_at=NOW,
            skills=load_skill_dictionary(),
            roles=load_role_rules(),
        )


def test_batch_validation_and_anomaly(source_configs: Any) -> None:
    recs, _ = _prepare(source_configs, "jobicy", load_fixture("jobicy_jobs.json")["jobs"])
    assert validate_batch(recs).passed
    assert validate_batch([]).passed
    dup = validate_batch([recs[0], recs[0]])
    assert not dup.passed and any("dedup_key" in f for f in dup.failures)
    assert count_anomaly(10, [100, 110, 90]) is not None
    assert count_anomaly(80, [100, 110, 90]) is None
    assert count_anomaly(1, [5, 5, 5]) is None  # tiny baselines are not judged
    assert count_anomaly(1, [100, 100]) is None  # not enough history


def test_overall_status() -> None:
    ok = SourceStats("a", success=True, complete=True)
    incomplete = SourceStats("b", success=True, complete=False)
    failed = SourceStats("c", success=False)
    assert _overall_status([ok]) == "succeeded"
    assert _overall_status([ok, incomplete]) == "partial"
    assert _overall_status([ok, failed]) == "partial"
    assert _overall_status([failed]) == "failed"
    assert _overall_status([]) == "failed"


# --- logging ------------------------------------------------------------------------------


def test_redaction_removes_credentials() -> None:
    text = (
        "could not connect postgresql://jmp_ingest:s3cr3t@ep-cool-1.eu-central-1.aws.neon.tech"
        "/db password=hunter2 token: abc"
    )
    cleaned = redact(text)
    assert "s3cr3t" not in cleaned and "hunter2" not in cleaned and "abc" not in cleaned
    assert "neon.tech" not in cleaned and "jmp_ingest" not in cleaned
    summary = safe_error_summary(RuntimeError("x" * 1000))
    assert len(summary) <= 300 and summary.startswith("RuntimeError")
