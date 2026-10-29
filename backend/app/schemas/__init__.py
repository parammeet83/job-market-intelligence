"""Public API response schemas (stable contract for the dashboard and BI consumers)."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Period(Schema):
    start: date
    end: date
    days: int


class Health(Schema):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable", "not_configured"]
    version: str


class LatestRun(Schema):
    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    trigger: str


class Summary(Schema):
    period: Period
    jobs_total: int
    jobs_active: int
    jobs_unconfirmed: int
    jobs_expired: int
    listings_in_period: int
    new_in_period: int
    observations_total: int
    skills_identified_active: int
    active_with_salary_info: int
    salary_disclosure_pct: float | None
    sources_enabled: int
    sources_healthy: int
    first_observation_date: date | None
    last_observation_date: date | None
    latest_run: LatestRun | None
    freshness: Literal["fresh", "delayed", "stale", "no_data"]
    hours_since_last_success: float | None
    skills_dictionary_version: str | None


class CountItem(Schema):
    label: str
    listings: int
    share_pct: float | None = None


class TimelinePoint(Schema):
    date: date
    listings_observed: int
    listings_first_seen: int
    reported_closed: int


class Timeline(Schema):
    period: Period
    points: list[TimelinePoint]


class JobSkill(Schema):
    slug: str
    name: str
    category: str


class JobListItem(Schema):
    id: int
    source_id: str
    source_name: str
    url: str
    title: str
    title_normalized: str
    role_category: str | None
    company: str | None
    location: str | None
    country: str | None
    work_mode: str | None
    work_mode_basis: str | None
    employment_type: str | None
    seniority: str | None
    salary_text: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    salary_period: str | None
    published_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    status: str
    skills: list[JobSkill]


class JobPage(Schema):
    items: list[JobListItem]
    total: int
    page: int
    page_size: int
    pages: int


class Observation(Schema):
    observation_date: date
    observation_method: str
    observed_status: str


class JobDetail(JobListItem):
    city: str | None
    region: str | None
    source_tags: list[str]
    last_verified_active_at: datetime | None
    status_changed_at: datetime
    source_reported_closed_at: datetime | None
    attribution: str
    skills_dictionary_version: str | None
    observations: list[Observation]


class SkillStat(Schema):
    slug: str
    name: str
    category: str
    listings: int
    eligible_listings: int
    share_pct: float | None
    prev_listings: int
    prev_eligible_listings: int
    prev_share_pct: float | None
    change_pct_points: float | None


class SkillList(Schema):
    period: Period
    previous_period: Period
    eligible_listings: int
    previous_eligible_listings: int
    dictionary_version: str | None
    small_sample: bool
    items: list[SkillStat]


class SkillTrendPoint(Schema):
    period: date
    slug: str
    listings: int
    eligible_listings: int
    share_pct: float | None


class SkillTrends(Schema):
    period: Period
    grain: Literal["day", "week"]
    skills: list[str]
    points: list[SkillTrendPoint]


class RoleAnalytics(Schema):
    period: Period
    population: int
    roles: list[CountItem]
    top_titles: list[CountItem]
    seniority: list[CountItem]
    top_companies: list[CountItem]
    listings_without_company: int


class WorkModeItem(Schema):
    work_mode: str
    basis: str
    listings: int


class LocationAnalytics(Schema):
    period: Period
    population: int
    countries: list[CountItem]
    locations: list[CountItem]
    work_modes: list[WorkModeItem]


class SalaryDisclosure(Schema):
    listings: int
    with_salary_info: int
    with_comparable_salary: int
    with_unit_unknown: int
    disclosure_pct: float | None
    comparable_pct: float | None


class SalaryGroup(Schema):
    currency: str
    period: str
    listings: int
    min_value: float
    p25: float
    median: float
    p75: float
    max_value: float


class SalaryRole(Schema):
    currency: str
    period: str
    role: str
    listings: int
    median: float


class SalaryTrendPoint(Schema):
    month: date
    currency: str
    period: str
    listings: int
    median: float


class SalaryAnalytics(Schema):
    period: Period
    disclosure: SalaryDisclosure
    groups: list[SalaryGroup]
    by_role: list[SalaryRole]
    trend: list[SalaryTrendPoint]
    min_group_size: int


class LifecycleItem(Schema):
    status: str
    listings: int
    avg_days_observed: float | None
    observed_7_days_or_more: int


class CoverageItem(Schema):
    source_id: str
    role: str
    listings: int
    with_country: int


class LifecycleAnalytics(Schema):
    period: Period
    statuses: list[LifecycleItem]
    coverage: list[CoverageItem]


class SourceInfo(Schema):
    source_id: str
    name: str
    enabled: bool
    access_method: str
    homepage_url: str
    attribution: str
    allow_row_export: bool
    disabled_reason: str | None
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_fetch_complete: bool | None
    last_record_count: int | None
    last_error_at: datetime | None
    last_error_summary: str | None
    jobs_total: int
    jobs_active: int
    observations_total: int
    first_seen_at: datetime | None
    health: Literal["healthy", "degraded", "failing", "never_run", "disabled"]


class IngestionRun(Schema):
    id: int
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    status: str
    skills_dictionary_version: str
    sources_attempted: int
    sources_succeeded: int
    records_fetched: int
    records_valid: int
    records_invalid: int
    records_out_of_scope: int
    duplicates: int
    jobs_inserted: int
    jobs_updated: int
    observations_written: int
    status_checks: int
    jobs_marked_expired: int
    jobs_marked_unconfirmed: int
    error_count: int
    error_summary: str | None
    quality_warnings: int
    quality_failures: int


class QualityResult(Schema):
    run_id: int
    source_id: str | None
    check_name: str
    outcome: str
    failed_count: int
    details: dict[str, Any]
    created_at: datetime


class FilterOptions(Schema):
    roles: list[CountItem]
    countries: list[CountItem]
    sources: list[CountItem]
    work_modes: list[CountItem]
    employment_types: list[CountItem]
    skill_categories: list[CountItem]
    skills: list[JobSkill]
