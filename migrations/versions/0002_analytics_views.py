"""analytics views (sql/views/v1_analytics_views.sql)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""

import os
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VIEWS_FILE = Path(__file__).resolve().parents[2] / "sql" / "views" / "v1_analytics_views.sql"
VIEW_NAMES = [
    "v_source_health",
    "v_salary_disclosure",
    "v_skill_share_active",
    "v_daily_listing_activity",
    "v_job_skills_current",
    "v_jobs_public",
]


def upgrade() -> None:
    op.execute(VIEWS_FILE.read_text(encoding="utf-8"))


def downgrade() -> None:
    # Views hold no data, but keep the same explicit opt-in as table downgrades.
    if os.environ.get("ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError("Set ALLOW_DESTRUCTIVE_DOWNGRADE=1 to drop analytics views.")
    for name in VIEW_NAMES:
        op.execute(f"DROP VIEW IF EXISTS {name}")
