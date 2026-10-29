"""Job listing queries shared by GET /jobs and the CSV export."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from sqlalchemy import (
    Connection,
    Select,
    and_,
    exists,
    func,
    literal,
    nulls_last,
    or_,
    select,
)

from backend.app.api.deps import like_pattern
from backend.app.models import job_skills, jobs, skills, sources

SortKey = Literal[
    "first_seen_desc",
    "last_seen_desc",
    "published_desc",
    "title_asc",
    "company_asc",
    "salary_desc",
]
SORTS = {
    "first_seen_desc": [jobs.c.first_seen_at.desc(), jobs.c.id.desc()],
    "last_seen_desc": [jobs.c.last_seen_at.desc(), jobs.c.id.desc()],
    "published_desc": [nulls_last(jobs.c.published_at.desc()), jobs.c.id.desc()],
    "title_asc": [jobs.c.title_normalized.asc(), jobs.c.id],
    "company_asc": [nulls_last(jobs.c.company.asc()), jobs.c.id],
    # Salary sort only orders listings within the same currency/period by value; listings
    # without a comparable salary come last. Currencies are not converted.
    "salary_desc": [
        nulls_last(jobs.c.salary_currency.asc()),
        nulls_last(func.coalesce(jobs.c.salary_max, jobs.c.salary_min).desc()),
        jobs.c.id.desc(),
    ],
}
JOB_COLUMNS = [
    jobs.c.id,
    jobs.c.source_id,
    sources.c.name.label("source_name"),
    jobs.c.canonical_url.label("url"),
    jobs.c.title_original.label("title"),
    jobs.c.title_normalized,
    jobs.c.role_category,
    jobs.c.company,
    jobs.c.location_original.label("location"),
    jobs.c.city,
    jobs.c.region,
    jobs.c.country,
    jobs.c.work_mode,
    jobs.c.work_mode_basis,
    jobs.c.employment_type,
    jobs.c.seniority,
    jobs.c.salary_text,
    jobs.c.salary_min,
    jobs.c.salary_max,
    jobs.c.salary_currency,
    jobs.c.salary_period,
    jobs.c.published_at,
    jobs.c.first_seen_at,
    jobs.c.last_seen_at,
    jobs.c.status,
    jobs.c.source_tags,
    jobs.c.last_verified_active_at,
    jobs.c.status_changed_at,
    jobs.c.source_reported_closed_at,
    jobs.c.skills_dictionary_version,
    sources.c.attribution,
    sources.c.allow_row_export,
]


@dataclass(frozen=True)
class JobFilters:
    q: str | None = None
    company: str | None = None
    role: str | None = None
    country: str | None = None
    source: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    skill: str | None = None
    salary_disclosed: bool | None = None
    status: Literal["active", "unconfirmed", "expired", "all"] = "active"
    first_seen_from: date | None = None
    first_seen_to: date | None = None


def _conditions(f: JobFilters) -> list[Any]:
    cond: list[Any] = []
    pattern = like_pattern(f.q)
    if pattern:
        cond.append(
            or_(
                jobs.c.title_original.ilike(pattern, escape="\\"),
                jobs.c.company.ilike(pattern, escape="\\"),
            )
        )
    if f.company:
        cond.append(jobs.c.company.ilike(like_pattern(f.company), escape="\\"))
    if f.role:
        cond.append(func.coalesce(jobs.c.role_category, literal("Unclassified")) == f.role)
    if f.country:
        cond.append(func.coalesce(jobs.c.country, literal("Unspecified")) == f.country)
    if f.source:
        cond.append(jobs.c.source_id == f.source)
    if f.work_mode:
        cond.append(jobs.c.work_mode == f.work_mode)
    if f.employment_type:
        cond.append(jobs.c.employment_type == f.employment_type)
    if f.status != "all":
        cond.append(jobs.c.status == f.status)
    if f.salary_disclosed is not None:
        disclosed = or_(
            jobs.c.salary_text.is_not(None),
            jobs.c.salary_min.is_not(None),
            jobs.c.salary_max.is_not(None),
        )
        cond.append(disclosed if f.salary_disclosed else ~disclosed)
    if f.first_seen_from:
        cond.append(func.date(func.timezone("UTC", jobs.c.first_seen_at)) >= f.first_seen_from)
    if f.first_seen_to:
        cond.append(func.date(func.timezone("UTC", jobs.c.first_seen_at)) <= f.first_seen_to)
    if f.skill:
        cond.append(
            exists().where(
                job_skills.c.job_id == jobs.c.id,
                job_skills.c.dictionary_version == jobs.c.skills_dictionary_version,
                job_skills.c.skill_id == skills.c.id,
                skills.c.slug == f.skill,
            )
        )
    return cond


def base_query(f: JobFilters, *, exportable_only: bool = False) -> Select[Any]:
    stmt = select(*JOB_COLUMNS).join(sources, sources.c.id == jobs.c.source_id)
    conditions = _conditions(f)
    if exportable_only:
        conditions.append(sources.c.allow_row_export.is_(True))
    return stmt.where(and_(*conditions)) if conditions else stmt


def count_jobs(conn: Connection, f: JobFilters) -> int:
    inner = base_query(f).with_only_columns(jobs.c.id).subquery()
    return int(conn.execute(select(func.count()).select_from(inner)).scalar_one())


def list_jobs(
    conn: Connection, f: JobFilters, sort: str, page: int, page_size: int
) -> list[dict[str, Any]]:
    stmt = base_query(f).order_by(*SORTS[sort]).limit(page_size).offset((page - 1) * page_size)
    return [dict(r._mapping) for r in conn.execute(stmt)]


def skills_for(conn: Connection, job_ids: list[int]) -> dict[int, list[dict[str, str]]]:
    if not job_ids:
        return {}
    rows = conn.execute(
        select(job_skills.c.job_id, skills.c.slug, skills.c.name, skills.c.category)
        .join(skills, skills.c.id == job_skills.c.skill_id)
        .join(
            jobs,
            and_(
                jobs.c.id == job_skills.c.job_id,
                jobs.c.skills_dictionary_version == job_skills.c.dictionary_version,
            ),
        )
        .where(job_skills.c.job_id.in_(job_ids))
        .order_by(skills.c.name)
    )
    result: dict[int, list[dict[str, str]]] = {}
    for r in rows:
        result.setdefault(r.job_id, []).append(
            {"slug": r.slug, "name": r.name, "category": r.category}
        )
    return result
