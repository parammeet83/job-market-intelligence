"""Validated query parameters shared by analytics endpoints."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import HTTPException, Query

MAX_RANGE_DAYS = 730
DEFAULT_RANGE_DAYS = 30
SourceId = Annotated[str | None, Query(pattern=r"^[a-z0-9_-]{1,40}$", description="Source id")]
Label = Annotated[str | None, Query(min_length=1, max_length=120)]
WorkModeParam = Annotated[Literal["remote", "hybrid", "onsite"] | None, Query()]


def today_utc() -> date:
    return datetime.now(UTC).date()


@dataclass(frozen=True)
class PeriodFilters:
    start: date
    end: date
    source: str | None
    role: str | None
    country: str | None
    work_mode: str | None

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def previous(self) -> tuple[date, date]:
        prev_end = self.start - timedelta(days=1)
        return prev_end - timedelta(days=self.days - 1), prev_end

    def params(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "source": self.source,
            "role": self.role,
            "country": self.country,
            "work_mode": self.work_mode,
        }


def period_filters(
    start: Annotated[date | None, Query(description="First UTC date (inclusive)")] = None,
    end: Annotated[date | None, Query(description="Last UTC date (inclusive)")] = None,
    source: SourceId = None,
    role: Label = None,
    country: Label = None,
    work_mode: WorkModeParam = None,
) -> PeriodFilters:
    end = end or today_utc()
    start = start or end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422, detail=f"date range is limited to {MAX_RANGE_DAYS} days"
        )
    return PeriodFilters(start, end, source, role, country, work_mode)


def like_pattern(value: str | None) -> str | None:
    """Escape LIKE wildcards in user input and wrap it for a contains-match."""
    if not value:
        return None
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
