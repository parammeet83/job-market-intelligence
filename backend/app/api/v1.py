"""Version 1 of the public, read-only API (mounted at /api/v1)."""

import math
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Connection, select, text

from backend.app.analytics.sql import query
from backend.app.api.deps import PeriodFilters, SourceId, like_pattern, period_filters
from backend.app.database import get_connection
from backend.app.models import job_observations, skills
from backend.app.schemas import (
    CountItem,
    CoverageItem,
    FilterOptions,
    IngestionRun,
    JobDetail,
    JobListItem,
    JobPage,
    JobSkill,
    LatestRun,
    LifecycleAnalytics,
    LifecycleItem,
    LocationAnalytics,
    Observation,
    Period,
    QualityResult,
    RoleAnalytics,
    SalaryAnalytics,
    SalaryDisclosure,
    SalaryGroup,
    SalaryRole,
    SalaryTrendPoint,
    SkillList,
    SkillStat,
    SkillTrendPoint,
    SkillTrends,
    SourceInfo,
    Summary,
    Timeline,
    TimelinePoint,
    WorkModeItem,
)
from backend.app.services import jobs as job_service

router = APIRouter()
Conn = Annotated[Connection, Depends(get_connection)]
Filters = Annotated[PeriodFilters, Depends(period_filters)]
SMALL_SAMPLE = 30
FRESH_HOURS, DELAYED_HOURS = 30, 54
HEALTHY_HOURS = 36
SALARY_MIN_GROUP = 3


def _period(f: PeriodFilters) -> Period:
    return Period(start=f.start, end=f.end, days=f.days)


def _rows(conn: Connection, name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r._mapping) for r in conn.execute(query(name), params)]


def _pct(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 2) if whole else None


def _with_share(items: list[dict[str, Any]], total: int) -> list[CountItem]:
    return [
        CountItem(
            label=str(i["label"]), listings=i["listings"], share_pct=_pct(i["listings"], total)
        )
        for i in items
    ]


def _current_dictionary_version(conn: Connection) -> str | None:
    return conn.execute(
        text("SELECT max(dictionary_version) FROM skills WHERE active")
    ).scalar_one_or_none()


@router.get("/summary", response_model=Summary, summary="Overview KPIs")
def summary(conn: Conn, f: Filters) -> Summary:
    row = _rows(conn, "summary", f.params())[0]
    latest = conn.execute(query("latest_run")).first()
    srcs = _rows(conn, "sources", {})
    now = datetime.now(UTC)
    enabled = [s for s in srcs if s["enabled"]]
    healthy = [s for s in enabled if _source_health(s, now) == "healthy"]
    hours = None
    freshness: Literal["fresh", "delayed", "stale", "no_data"] = "no_data"
    if latest is not None:
        hours = round((now - (latest.finished_at or latest.started_at)).total_seconds() / 3600, 1)
        freshness = (
            "fresh" if hours <= FRESH_HOURS else "delayed" if hours <= DELAYED_HOURS else "stale"
        )
    return Summary(
        period=_period(f),
        **row,
        salary_disclosure_pct=_pct(row["active_with_salary_info"], row["jobs_active"]),
        sources_enabled=len(enabled),
        sources_healthy=len(healthy),
        latest_run=LatestRun(**latest._mapping) if latest is not None else None,
        freshness=freshness,
        hours_since_last_success=hours,
        skills_dictionary_version=_current_dictionary_version(conn),
    )


@router.get("/analytics/timeline", response_model=Timeline, summary="Daily listing activity")
def timeline(conn: Conn, f: Filters) -> Timeline:
    points = [TimelinePoint(**r) for r in _rows(conn, "timeline", f.params())]
    return Timeline(period=_period(f), points=points)


@router.get("/jobs", response_model=JobPage, summary="Search and filter job listings")
def list_jobs(
    conn: Conn,
    q: Annotated[str | None, Query(max_length=100, description="Title/company search")] = None,
    company: Annotated[str | None, Query(max_length=120)] = None,
    role: Annotated[str | None, Query(max_length=120)] = None,
    country: Annotated[str | None, Query(max_length=120)] = None,
    source: SourceId = None,
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None,
    employment_type: Literal[
        "full_time", "part_time", "contract", "temporary", "internship", "freelance"
    ]
    | None = None,
    skill: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{1,60}$")] = None,
    salary_disclosed: bool | None = None,
    status: Literal["active", "unconfirmed", "expired", "all"] = "active",
    sort: job_service.SortKey = "first_seen_desc",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> JobPage:
    f = job_service.JobFilters(
        q=q,
        company=company,
        role=role,
        country=country,
        source=source,
        work_mode=work_mode,
        employment_type=employment_type,
        skill=skill,
        salary_disclosed=salary_disclosed,
        status=status,
    )
    total = job_service.count_jobs(conn, f)
    rows = job_service.list_jobs(conn, f, sort, page, page_size)
    skill_map = job_service.skills_for(conn, [r["id"] for r in rows])
    items = [JobListItem.model_validate({**r, "skills": skill_map.get(r["id"], [])}) for r in rows]
    return JobPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobDetail,
    summary="One listing with history",
    responses={404: {"description": "Not found"}},
)
def job_detail(conn: Conn, job_id: Annotated[int, Path(ge=1, le=2**62)]) -> JobDetail:
    stmt = job_service.base_query(job_service.JobFilters(status="all")).where(
        job_service.jobs.c.id == job_id
    )
    row = conn.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    data = dict(row._mapping)
    obs = conn.execute(
        select(
            job_observations.c.observation_date,
            job_observations.c.observation_method,
            job_observations.c.observed_status,
        )
        .where(job_observations.c.job_id == job_id)
        .order_by(job_observations.c.observation_date.desc())
        .limit(120)
    )
    return JobDetail.model_validate(
        {
            **data,
            "skills": job_service.skills_for(conn, [job_id]).get(job_id, []),
            "observations": [Observation(**o._mapping) for o in obs],
        }
    )


@router.get("/skills", response_model=SkillList, summary="Skill ranking and share")
def skill_ranking(
    conn: Conn,
    f: Filters,
    category: Annotated[str | None, Query(max_length=60)] = None,
    q: Annotated[str | None, Query(max_length=60)] = None,
) -> SkillList:
    prev_start, prev_end = f.previous
    rows = _rows(
        conn,
        "skills",
        {
            **f.params(),
            "prev_start": prev_start,
            "prev_end": prev_end,
            "category": category,
            "q": like_pattern(q),
        },
    )
    eligible = rows[0]["eligible_listings"] if rows else 0
    prev_eligible = rows[0]["prev_eligible_listings"] if rows else 0
    items = []
    for r in rows:
        change = None
        if r["share_pct"] is not None and r["prev_share_pct"] is not None:
            change = round(float(r["share_pct"]) - float(r["prev_share_pct"]), 2)
        items.append(SkillStat(**r, change_pct_points=change))
    if not rows:
        eligible = _rows(conn, "summary", f.params())[0]["listings_in_period"]
    return SkillList(
        period=_period(f),
        previous_period=Period(start=prev_start, end=prev_end, days=f.days),
        eligible_listings=eligible,
        previous_eligible_listings=prev_eligible,
        dictionary_version=_current_dictionary_version(conn),
        small_sample=eligible < SMALL_SAMPLE,
        items=items,
    )


@router.get("/skills/trends", response_model=SkillTrends, summary="Skill share over time")
def skill_trends(
    conn: Conn,
    f: Filters,
    skill: Annotated[
        list[str], Query(min_length=1, max_length=8, description="Skill slugs (repeatable, max 8)")
    ],
    grain: Literal["day", "week"] = "day",
) -> SkillTrends:
    for slug in skill:
        if not slug or len(slug) > 60 or not all(c.isalnum() or c == "-" for c in slug):
            raise HTTPException(status_code=422, detail="invalid skill slug")
    rows = _rows(conn, "skill_trends", {**f.params(), "skills": skill, "grain": grain})
    return SkillTrends(
        period=_period(f), grain=grain, skills=skill, points=[SkillTrendPoint(**r) for r in rows]
    )


@router.get(
    "/analytics/roles",
    response_model=RoleAnalytics,
    summary="Roles, titles, seniority and employers",
)
def role_analytics(
    conn: Conn, f: Filters, limit: Annotated[int, Query(ge=5, le=50)] = 15
) -> RoleAnalytics:
    p = f.params()
    population = _rows(conn, "summary", p)[0]["listings_in_period"]
    companies = _rows(conn, "top_companies", {**p, "limit": limit})
    without_company = population - sum(
        r["listings"] for r in _rows(conn, "top_companies", {**p, "limit": 1_000_000})
    )
    return RoleAnalytics(
        period=_period(f),
        population=population,
        roles=_with_share(_rows(conn, "roles", p), population),
        top_titles=_with_share(_rows(conn, "top_titles", {**p, "limit": limit}), population),
        seniority=_with_share(_rows(conn, "seniority", p), population),
        top_companies=_with_share(companies, population),
        listings_without_company=without_company,
    )


@router.get(
    "/analytics/locations",
    response_model=LocationAnalytics,
    summary="Countries, location strings and work modes",
)
def location_analytics(
    conn: Conn, f: Filters, limit: Annotated[int, Query(ge=5, le=50)] = 15
) -> LocationAnalytics:
    p = f.params()
    population = _rows(conn, "summary", p)[0]["listings_in_period"]
    return LocationAnalytics(
        period=_period(f),
        population=population,
        countries=_with_share(_rows(conn, "countries", p), population),
        locations=_with_share(_rows(conn, "location_strings", {**p, "limit": limit}), population),
        work_modes=[WorkModeItem(**r) for r in _rows(conn, "work_modes", p)],
    )


@router.get(
    "/analytics/salaries",
    response_model=SalaryAnalytics,
    summary="Salary disclosure and distributions per currency and period",
)
def salary_analytics(conn: Conn, f: Filters) -> SalaryAnalytics:
    p = f.params()
    d = _rows(conn, "salary_disclosure", p)[0]
    disclosure = SalaryDisclosure(
        **d,
        disclosure_pct=_pct(d["with_salary_info"], d["listings"]),
        comparable_pct=_pct(d["with_comparable_salary"], d["listings"]),
    )
    return SalaryAnalytics(
        period=_period(f),
        disclosure=disclosure,
        groups=[SalaryGroup(**r) for r in _rows(conn, "salary_groups", p)],
        by_role=[
            SalaryRole(**r) for r in _rows(conn, "salary_by_role", {**p, "min_n": SALARY_MIN_GROUP})
        ],
        trend=[
            SalaryTrendPoint(**r)
            for r in _rows(conn, "salary_trend", {**p, "min_n": SALARY_MIN_GROUP})
        ],
        min_group_size=SALARY_MIN_GROUP,
    )


@router.get(
    "/analytics/lifecycle",
    response_model=LifecycleAnalytics,
    summary="Listing persistence and source coverage",
)
def lifecycle_analytics(conn: Conn, f: Filters) -> LifecycleAnalytics:
    p = f.params()
    return LifecycleAnalytics(
        period=_period(f),
        statuses=[LifecycleItem(**r) for r in _rows(conn, "lifecycle", p)],
        coverage=[CoverageItem(**r) for r in _rows(conn, "coverage", p)],
    )


SourceHealth = Literal["healthy", "degraded", "failing", "never_run", "disabled"]


def _source_health(s: dict[str, Any], now: datetime) -> SourceHealth:
    if not s["enabled"]:
        return "disabled"
    if s["last_attempt_at"] is None:
        return "never_run"
    if s["last_success_at"] is None or (
        s["last_error_at"] is not None
        and s["last_error_at"] >= s["last_success_at"]
        and not s["last_fetch_complete"]
    ):
        return "failing"
    if now - s["last_success_at"] > timedelta(hours=HEALTHY_HOURS) or not s["last_fetch_complete"]:
        return "degraded"
    return "healthy"


@router.get("/sources", response_model=list[SourceInfo], summary="Sources, health, attribution")
def list_sources(conn: Conn) -> list[SourceInfo]:
    now = datetime.now(UTC)
    return [SourceInfo(**s, health=_source_health(s, now)) for s in _rows(conn, "sources", {})]


@router.get("/ingestion-runs", response_model=list[IngestionRun], summary="Ingestion audit log")
def ingestion_runs(
    conn: Conn, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[IngestionRun]:
    return [IngestionRun(**r) for r in _rows(conn, "ingestion_runs", {"limit": limit})]


@router.get(
    "/data-quality",
    response_model=list[QualityResult],
    summary="Data-quality results (latest run by default)",
)
def data_quality(
    conn: Conn, run_id: Annotated[int | None, Query(ge=1)] = None
) -> list[QualityResult]:
    return [QualityResult(**r) for r in _rows(conn, "data_quality", {"run_id": run_id})]


@router.get("/meta/filters", response_model=FilterOptions, summary="Values for filter controls")
def filter_options(conn: Conn) -> FilterOptions:
    groups: dict[str, list[CountItem]] = {}
    for r in _rows(conn, "filter_options", {}):
        groups.setdefault(r["kind"], []).append(CountItem(label=r["value"], listings=r["n"]))
    skill_rows = conn.execute(
        select(skills.c.slug, skills.c.name, skills.c.category)
        .where(skills.c.active)
        .order_by(skills.c.name)
    )
    return FilterOptions(
        roles=groups.get("role", []),
        countries=groups.get("country", []),
        sources=groups.get("source", []),
        work_modes=groups.get("work_mode", []),
        employment_types=groups.get("employment_type", []),
        skill_categories=groups.get("skill_category", []),
        skills=[JobSkill(**s._mapping) for s in skill_rows],
    )
