"""CSV exports. Row-level exports include only sources whose terms permit redistribution
(sources.allow_row_export); aggregate exports cover all sources. Cells that a spreadsheet
could interpret as a formula are prefixed with an apostrophe."""

import csv
import io
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Connection, select

from backend.app.analytics.sql import query
from backend.app.api.deps import PeriodFilters, SourceId, period_filters
from backend.app.database import get_connection
from backend.app.models import job_observations, jobs, sources
from backend.app.services import jobs as job_service

router = APIRouter(prefix="/exports", tags=["exports"])
Conn = Annotated[Connection, Depends(get_connection)]
MAX_JOB_ROWS = 5000
MAX_OBSERVATION_ROWS = 50_000
JOB_FIELDS = [
    "id",
    "source_name",
    "url",
    "title",
    "title_normalized",
    "role_category",
    "company",
    "location",
    "city",
    "region",
    "country",
    "work_mode",
    "work_mode_basis",
    "employment_type",
    "seniority",
    "salary_text",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "published_at",
    "first_seen_at",
    "last_seen_at",
    "status",
    "attribution",
]


def safe_cell(value: Any) -> Any:
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


def _stream(header: list[str], rows: Iterable[dict[str, Any]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    yield buffer.getvalue()
    for row in rows:
        buffer.seek(0)
        buffer.truncate()
        writer.writerow([safe_cell(row.get(h)) for h in header])
        yield buffer.getvalue()


def _csv_response(name: str, header: list[str], rows: list[dict[str, Any]]) -> StreamingResponse:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return StreamingResponse(
        _stream(header, rows),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="jobmarket-pulse-{name}-{stamp}.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/jobs.csv", summary="Normalized listings (redistributable sources only)")
def export_jobs(
    conn: Conn,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: Annotated[str | None, Query(max_length=120)] = None,
    country: Annotated[str | None, Query(max_length=120)] = None,
    source: SourceId = None,
    skill: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{1,60}$")] = None,
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None,
    status: Literal["active", "unconfirmed", "expired", "all"] = "active",
) -> StreamingResponse:
    f = job_service.JobFilters(
        q=q,
        role=role,
        country=country,
        source=source,
        skill=skill,
        work_mode=work_mode,
        status=status,
    )
    stmt = (
        job_service.base_query(f, exportable_only=True)
        .order_by(*job_service.SORTS["first_seen_desc"])
        .limit(MAX_JOB_ROWS)
    )
    rows = [dict(r._mapping) for r in conn.execute(stmt)]
    return _csv_response("jobs", JOB_FIELDS, rows)


@router.get("/skills.csv", summary="Skill counts and shares (aggregate, all sources)")
def export_skills(
    conn: Conn, f: Annotated[PeriodFilters, Depends(period_filters)]
) -> StreamingResponse:
    prev_start, prev_end = f.previous
    rows = [
        dict(r._mapping)
        for r in conn.execute(
            query("skills"),
            {
                **f.params(),
                "prev_start": prev_start,
                "prev_end": prev_end,
                "category": None,
                "q": None,
            },
        )
    ]
    for r in rows:
        r["period_start"], r["period_end"] = f.start, f.end
    header = [
        "period_start",
        "period_end",
        "slug",
        "name",
        "category",
        "listings",
        "eligible_listings",
        "share_pct",
        "prev_listings",
        "prev_eligible_listings",
        "prev_share_pct",
    ]
    return _csv_response("skills", header, rows)


@router.get(
    "/observations.csv", summary="Historical daily observations (redistributable sources only)"
)
def export_observations(
    conn: Conn, f: Annotated[PeriodFilters, Depends(period_filters)]
) -> StreamingResponse:
    stmt = (
        select(
            job_observations.c.job_id,
            job_observations.c.observation_date,
            job_observations.c.observation_method,
            job_observations.c.observed_status,
            job_observations.c.source_id,
            job_observations.c.role_category,
            job_observations.c.title_normalized,
            job_observations.c.work_mode,
            job_observations.c.salary_min,
            job_observations.c.salary_max,
            job_observations.c.salary_currency,
            job_observations.c.salary_period,
            jobs.c.canonical_url.label("url"),
        )
        .join(jobs, jobs.c.id == job_observations.c.job_id)
        .join(sources, sources.c.id == job_observations.c.source_id)
        .where(
            sources.c.allow_row_export.is_(True),
            job_observations.c.observation_date.between(f.start, f.end),
        )
        .order_by(job_observations.c.observation_date, job_observations.c.job_id)
        .limit(MAX_OBSERVATION_ROWS)
    )
    if f.source:
        stmt = stmt.where(job_observations.c.source_id == f.source)
    if f.role:
        stmt = stmt.where(job_observations.c.role_category == f.role)
    rows = [dict(r._mapping) for r in conn.execute(stmt)]
    header = [
        "job_id",
        "observation_date",
        "observation_method",
        "observed_status",
        "source_id",
        "role_category",
        "title_normalized",
        "work_mode",
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_period",
        "url",
    ]
    return _csv_response("observations", header, rows)
