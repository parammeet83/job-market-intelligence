"""SQLAlchemy Core table definitions (the schema is created by Alembic migrations, never here)."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

metadata = MetaData()

WORK_MODES = ("remote", "hybrid", "onsite")
JOB_STATUSES = ("active", "unconfirmed", "expired")
SALARY_PERIODS = ("hour", "day", "week", "month", "year")
RUN_STATUSES = ("running", "succeeded", "partial", "failed")


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IS NULL OR {column} IN ({quoted})"


sources = Table(
    "sources",
    metadata,
    Column("id", String(40), primary_key=True),
    Column("name", Text, nullable=False),
    Column("homepage_url", Text, nullable=False),
    Column("api_url", Text, nullable=False),
    Column("docs_url", Text),
    Column("access_method", Text, nullable=False),
    Column("attribution", Text, nullable=False),
    Column("enabled", Boolean, nullable=False, server_default=text("false")),
    Column("allow_row_export", Boolean, nullable=False, server_default=text("false")),
    Column("disabled_reason", Text),
    Column("last_attempt_at", DateTime(timezone=True)),
    Column("last_success_at", DateTime(timezone=True)),
    Column("last_error_at", DateTime(timezone=True)),
    Column("last_error_summary", Text),
    Column("last_fetch_complete", Boolean),
    Column("last_record_count", Integer),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

ingestion_runs = Table(
    "ingestion_runs",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    Column("trigger", String(20), nullable=False),
    Column("status", String(12), nullable=False, server_default=text("'running'")),
    Column("skills_dictionary_version", String(20), nullable=False),
    Column("sources_attempted", Integer, nullable=False, server_default=text("0")),
    Column("sources_succeeded", Integer, nullable=False, server_default=text("0")),
    Column("records_fetched", Integer, nullable=False, server_default=text("0")),
    Column("records_valid", Integer, nullable=False, server_default=text("0")),
    Column("records_invalid", Integer, nullable=False, server_default=text("0")),
    Column("records_out_of_scope", Integer, nullable=False, server_default=text("0")),
    Column("duplicates", Integer, nullable=False, server_default=text("0")),
    Column("jobs_inserted", Integer, nullable=False, server_default=text("0")),
    Column("jobs_updated", Integer, nullable=False, server_default=text("0")),
    Column("observations_written", Integer, nullable=False, server_default=text("0")),
    Column("skill_links_written", Integer, nullable=False, server_default=text("0")),
    Column("status_checks", Integer, nullable=False, server_default=text("0")),
    Column("jobs_marked_expired", Integer, nullable=False, server_default=text("0")),
    Column("jobs_marked_unconfirmed", Integer, nullable=False, server_default=text("0")),
    Column("error_count", Integer, nullable=False, server_default=text("0")),
    Column("error_summary", Text),
    Column("details", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint(_in("status", RUN_STATUSES), name="ck_ingestion_runs_status"),
    CheckConstraint(
        "trigger IN ('cli', 'schedule', 'manual', 'test')", name="ck_ingestion_runs_trigger"
    ),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("source_id", String(40), ForeignKey("sources.id"), nullable=False),
    Column("source_job_id", Text),
    Column("canonical_url", Text, nullable=False),
    Column("dedup_key", Text, nullable=False, unique=True),
    Column("cross_source_key", Text, nullable=False),
    Column("title_original", Text, nullable=False),
    Column("title_normalized", Text, nullable=False),
    Column("role_category", Text),
    Column("company", Text),
    Column("location_original", Text),
    Column("city", Text),
    Column("region", Text),
    Column("country", Text),
    Column("work_mode", String(10)),
    Column("work_mode_basis", String(20)),
    Column("employment_type", String(20)),
    Column("seniority", String(20)),
    Column("salary_text", Text),
    Column("salary_min", Numeric(14, 2)),
    Column("salary_max", Numeric(14, 2)),
    Column("salary_currency", String(3)),
    Column("salary_period", String(5)),
    Column("source_tags", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")),
    Column("published_at", DateTime(timezone=True)),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("last_verified_active_at", DateTime(timezone=True)),
    Column("status", String(12), nullable=False, server_default=text("'active'")),
    Column("status_changed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("source_reported_closed_at", DateTime(timezone=True)),
    Column("consecutive_misses", Integer, nullable=False, server_default=text("0")),
    Column("skills_dictionary_version", String(20)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(_in("work_mode", WORK_MODES), name="ck_jobs_work_mode"),
    CheckConstraint(f"status IN {JOB_STATUSES}", name="ck_jobs_status"),
    CheckConstraint(_in("salary_period", SALARY_PERIODS), name="ck_jobs_salary_period"),
    CheckConstraint(
        "salary_currency IS NULL OR salary_currency ~ '^[A-Z]{3}$'", name="ck_jobs_currency"
    ),
    CheckConstraint(
        "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
        name="ck_jobs_salary_range",
    ),
    CheckConstraint(
        "(salary_min IS NULL OR salary_min > 0) AND (salary_max IS NULL OR salary_max > 0)",
        name="ck_jobs_salary_positive",
    ),
    CheckConstraint("first_seen_at <= last_seen_at", name="ck_jobs_seen_order"),
    Index(
        "uq_jobs_source_native_id",
        "source_id",
        "source_job_id",
        unique=True,
        postgresql_where=text("source_job_id IS NOT NULL"),
    ),
    Index("ix_jobs_status", "status"),
    Index("ix_jobs_first_seen_at", "first_seen_at"),
    Index("ix_jobs_last_seen_at", "last_seen_at"),
    Index("ix_jobs_role_category", "role_category"),
    Index("ix_jobs_country", "country"),
    Index("ix_jobs_company", "company"),
    Index("ix_jobs_source_status", "source_id", "status"),
)

job_observations = Table(
    "job_observations",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_id", BigInteger, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", BigInteger, ForeignKey("ingestion_runs.id"), nullable=False),
    Column("source_id", String(40), ForeignKey("sources.id"), nullable=False),
    Column("observation_date", Date, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("observation_method", String(12), nullable=False),
    Column("observed_status", String(12), nullable=False),
    Column("title_normalized", Text),
    Column("role_category", Text),
    Column("work_mode", String(10)),
    Column("salary_min", Numeric(14, 2)),
    Column("salary_max", Numeric(14, 2)),
    Column("salary_currency", String(3)),
    Column("salary_period", String(5)),
    UniqueConstraint("job_id", "observation_date", name="uq_job_observations_job_date"),
    CheckConstraint(
        "observation_method IN ('feed', 'status_check')", name="ck_job_observations_method"
    ),
    CheckConstraint(f"observed_status IN {JOB_STATUSES}", name="ck_job_observations_status"),
    Index("ix_job_observations_date", "observation_date"),
    Index("ix_job_observations_run", "run_id"),
)

skills = Table(
    "skills",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("slug", String(60), nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("aliases", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")),
    Column("dictionary_version", String(20), nullable=False),
    Column("active", Boolean, nullable=False, server_default=text("true")),
)

job_skills = Table(
    "job_skills",
    metadata,
    Column("job_id", BigInteger, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id"), primary_key=True),
    Column("dictionary_version", String(20), primary_key=True),
    Column("matched_in", ARRAY(Text), nullable=False),
    Column("detected_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_job_skills_skill_version", "skill_id", "dictionary_version"),
)

# Transient copy of description text, used only to re-run skill extraction after a dictionary
# change. Never exposed by the API; purged after the source's retention window.
job_descriptions = Table(
    "job_descriptions",
    metadata,
    Column("job_id", BigInteger, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("text_plain", Text, nullable=False),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("purge_after", DateTime(timezone=True), nullable=False),
    Index("ix_job_descriptions_purge_after", "purge_after"),
)

data_quality_results = Table(
    "data_quality_results",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_id", BigInteger, ForeignKey("ingestion_runs.id"), nullable=False),
    Column("source_id", String(40), ForeignKey("sources.id")),
    Column("check_name", String(60), nullable=False),
    Column("outcome", String(6), nullable=False),
    Column("failed_count", Integer, nullable=False, server_default=text("0")),
    Column("details", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("outcome IN ('pass', 'warn', 'fail')", name="ck_dq_outcome"),
    Index("ix_dq_run", "run_id"),
)
