"""Canonical job record contract. Every record is validated before it can be persisted."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.ingestion.transformations.salary import SALARY_PERIOD_VALUES, check_salary

WorkMode = Literal["remote", "hybrid", "onsite"]
EmploymentType = Literal[
    "full_time", "part_time", "contract", "temporary", "internship", "freelance"
]
Seniority = Literal[
    "intern",
    "junior",
    "mid",
    "senior",
    "lead",
    "staff",
    "principal",
    "manager",
    "director",
    "executive",
]
EARLIEST_PLAUSIBLE = datetime(2000, 1, 1, tzinfo=UTC)


class JobRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1, max_length=40)
    source_job_id: str | None = Field(default=None, max_length=200)
    canonical_url: str = Field(min_length=10, max_length=2000)
    allowed_hosts: tuple[str, ...] = Field(exclude=True)
    dedup_key: str = Field(min_length=3, max_length=2100)
    cross_source_key: str = Field(min_length=8, max_length=64)
    title_original: str = Field(min_length=1, max_length=500)
    title_normalized: str = Field(min_length=1, max_length=500)
    role_category: str | None = None
    company: str | None = Field(default=None, max_length=300)
    location_original: str | None = Field(default=None, max_length=500)
    city: str | None = None
    region: str | None = None
    country: str | None = None
    work_mode: WorkMode | None = None
    work_mode_basis: Literal["text", "source_default"] | None = None
    employment_type: EmploymentType | None = None
    seniority: Seniority | None = None
    salary_text: str | None = Field(default=None, max_length=300)
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    salary_period: str | None = None
    source_tags: tuple[str, ...] = ()
    published_at: datetime | None = None
    observed_at: datetime
    description_text: str = Field(default="", exclude=True)
    skills: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("canonical_url")
    @classmethod
    def _https_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("canonical_url must be an absolute https URL")
        return value

    @field_validator("salary_period")
    @classmethod
    def _period(cls, value: str | None) -> str | None:
        if value is not None and value not in SALARY_PERIOD_VALUES:
            raise ValueError("invalid salary period")
        return value

    @field_validator("published_at", "observed_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _cross_field(self) -> "JobRecord":
        host = (urlsplit(self.canonical_url).hostname or "").lower()
        if self.allowed_hosts and host not in self.allowed_hosts:
            raise ValueError("canonical_url host is not the source's host")
        if self.published_at is not None:
            if self.published_at < EARLIEST_PLAUSIBLE:
                raise ValueError("published_at implausibly old")
            if self.published_at > self.observed_at + timedelta(days=2):
                raise ValueError("published_at is in the future")
        issue = check_salary(
            self.salary_min, self.salary_max, self.salary_currency, self.salary_period
        )
        if issue:
            raise ValueError(f"salary: {issue}")
        if (self.salary_currency or self.salary_period) and (
            self.salary_min is None and self.salary_max is None
        ):
            raise ValueError("salary currency/period without an amount")
        return self


def reason_code(exc: Exception) -> str:
    """Compact, safe reason for an invalid record (field names + messages, no values)."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        parts = []
        for err in errors()[:3]:
            loc = ".".join(str(p) for p in err.get("loc", ())) or "record"
            parts.append(f"{loc}: {err.get('msg', 'invalid')}")
        return "; ".join(parts)[:200]
    return str(exc)[:200]
