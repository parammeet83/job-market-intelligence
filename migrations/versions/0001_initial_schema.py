"""initial schema

Reviewed: tables, constraints and indexes for sources, jobs, job_observations, skills,
job_skills, job_descriptions, ingestion_runs and data_quality_results.

Revision ID: 0001
Revises:
Create Date: 2026-10-29 11:28:42.157046
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'running'"), nullable=False
        ),
        sa.Column("skills_dictionary_version", sa.String(length=20), nullable=False),
        sa.Column("sources_attempted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sources_succeeded", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_fetched", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_valid", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_invalid", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "records_out_of_scope", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("duplicates", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("jobs_inserted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("jobs_updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "observations_written", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("skill_links_written", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status_checks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("jobs_marked_expired", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "jobs_marked_unconfirmed", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("error_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IS NULL OR status IN ('running', 'succeeded', 'partial', 'failed')",
            name="ck_ingestion_runs_status",
        ),
        sa.CheckConstraint(
            "trigger IN ('cli', 'schedule', 'manual', 'test')", name="ck_ingestion_runs_trigger"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("dictionary_version", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("homepage_url", sa.Text(), nullable=False),
        sa.Column("api_url", sa.Text(), nullable=False),
        sa.Column("docs_url", sa.Text(), nullable=True),
        sa.Column("access_method", sa.Text(), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "allow_row_export", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("last_fetch_complete", sa.Boolean(), nullable=True),
        sa.Column("last_record_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "data_quality_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=True),
        sa.Column("check_name", sa.String(length=60), nullable=False),
        sa.Column("outcome", sa.String(length=6), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("outcome IN ('pass', 'warn', 'fail')", name="ck_dq_outcome"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["ingestion_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dq_run", "data_quality_results", ["run_id"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("source_job_id", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column("cross_source_key", sa.Text(), nullable=False),
        sa.Column("title_original", sa.Text(), nullable=False),
        sa.Column("title_normalized", sa.Text(), nullable=False),
        sa.Column("role_category", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("location_original", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("work_mode", sa.String(length=10), nullable=True),
        sa.Column("work_mode_basis", sa.String(length=20), nullable=True),
        sa.Column("employment_type", sa.String(length=20), nullable=True),
        sa.Column("seniority", sa.String(length=20), nullable=True),
        sa.Column("salary_text", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("salary_period", sa.String(length=5), nullable=True),
        sa.Column(
            "source_tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column(
            "status_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source_reported_closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_misses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skills_dictionary_version", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "salary_currency IS NULL OR salary_currency ~ '^[A-Z]{3}$'", name="ck_jobs_currency"
        ),
        sa.CheckConstraint(
            "salary_period IS NULL OR salary_period IN ('hour', 'day', 'week', 'month', 'year')",
            name="ck_jobs_salary_period",
        ),
        sa.CheckConstraint("status IN ('active', 'unconfirmed', 'expired')", name="ck_jobs_status"),
        sa.CheckConstraint(
            "work_mode IS NULL OR work_mode IN ('remote', 'hybrid', 'onsite')",
            name="ck_jobs_work_mode",
        ),
        sa.CheckConstraint(
            "(salary_min IS NULL OR salary_min > 0) AND (salary_max IS NULL OR salary_max > 0)",
            name="ck_jobs_salary_positive",
        ),
        sa.CheckConstraint("first_seen_at <= last_seen_at", name="ck_jobs_seen_order"),
        sa.CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="ck_jobs_salary_range",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key"),
    )
    op.create_index("ix_jobs_company", "jobs", ["company"], unique=False)
    op.create_index("ix_jobs_country", "jobs", ["country"], unique=False)
    op.create_index("ix_jobs_first_seen_at", "jobs", ["first_seen_at"], unique=False)
    op.create_index("ix_jobs_last_seen_at", "jobs", ["last_seen_at"], unique=False)
    op.create_index("ix_jobs_role_category", "jobs", ["role_category"], unique=False)
    op.create_index("ix_jobs_source_status", "jobs", ["source_id", "status"], unique=False)
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)
    op.create_index(
        "uq_jobs_source_native_id",
        "jobs",
        ["source_id", "source_job_id"],
        unique=True,
        postgresql_where=sa.text("source_job_id IS NOT NULL"),
    )
    op.create_table(
        "job_descriptions",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("text_plain", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "ix_job_descriptions_purge_after", "job_descriptions", ["purge_after"], unique=False
    )
    op.create_table(
        "job_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_method", sa.String(length=12), nullable=False),
        sa.Column("observed_status", sa.String(length=12), nullable=False),
        sa.Column("title_normalized", sa.Text(), nullable=True),
        sa.Column("role_category", sa.Text(), nullable=True),
        sa.Column("work_mode", sa.String(length=10), nullable=True),
        sa.Column("salary_min", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("salary_period", sa.String(length=5), nullable=True),
        sa.CheckConstraint(
            "observation_method IN ('feed', 'status_check')", name="ck_job_observations_method"
        ),
        sa.CheckConstraint(
            "observed_status IN ('active', 'unconfirmed', 'expired')",
            name="ck_job_observations_status",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["ingestion_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "observation_date", name="uq_job_observations_job_date"),
    )
    op.create_index(
        "ix_job_observations_date", "job_observations", ["observation_date"], unique=False
    )
    op.create_index("ix_job_observations_run", "job_observations", ["run_id"], unique=False)
    op.create_table(
        "job_skills",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("dictionary_version", sa.String(length=20), nullable=False),
        sa.Column("matched_in", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
        ),
        sa.PrimaryKeyConstraint("job_id", "skill_id", "dictionary_version"),
    )
    op.create_index(
        "ix_job_skills_skill_version",
        "job_skills",
        ["skill_id", "dictionary_version"],
        unique=False,
    )


def downgrade() -> None:
    if os.environ.get("ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "Refusing to drop all tables. Set ALLOW_DESTRUCTIVE_DOWNGRADE=1 "
            "only on a disposable database."
        )
    op.drop_index("ix_job_skills_skill_version", table_name="job_skills")
    op.drop_table("job_skills")
    op.drop_index("ix_job_observations_run", table_name="job_observations")
    op.drop_index("ix_job_observations_date", table_name="job_observations")
    op.drop_table("job_observations")
    op.drop_index("ix_job_descriptions_purge_after", table_name="job_descriptions")
    op.drop_table("job_descriptions")
    op.drop_index(
        "uq_jobs_source_native_id",
        table_name="jobs",
        postgresql_where=sa.text("source_job_id IS NOT NULL"),
    )
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_source_status", table_name="jobs")
    op.drop_index("ix_jobs_role_category", table_name="jobs")
    op.drop_index("ix_jobs_last_seen_at", table_name="jobs")
    op.drop_index("ix_jobs_first_seen_at", table_name="jobs")
    op.drop_index("ix_jobs_country", table_name="jobs")
    op.drop_index("ix_jobs_company", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_dq_run", table_name="data_quality_results")
    op.drop_table("data_quality_results")
    op.drop_table("sources")
    op.drop_table("skills")
    op.drop_table("ingestion_runs")
