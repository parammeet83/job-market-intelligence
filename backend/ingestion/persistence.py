"""Database writes for the ingestion pipeline (writer role). All statements are idempotent:
re-running the same data on the same UTC day produces no duplicate jobs, observations or
skill links."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Connection, func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from backend.app.models import (
    data_quality_results,
    ingestion_runs,
    job_descriptions,
    job_observations,
    job_skills,
    jobs,
    skills,
    sources,
)
from backend.ingestion.config import SourceConfig
from backend.ingestion.skills.extractor import SkillDictionary
from backend.ingestion.validation.contracts import JobRecord

CHUNK = 500


def _chunks(items: Sequence[Any], size: int = CHUNK) -> list[Sequence[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def sync_sources(conn: Connection, configs: Sequence[SourceConfig]) -> None:
    for cfg in configs:
        values = {
            "id": cfg.id,
            "name": cfg.name,
            "homepage_url": cfg.homepage_url,
            "api_url": cfg.api_url,
            "docs_url": cfg.docs_url,
            "access_method": cfg.access_method,
            "attribution": cfg.attribution,
            "enabled": cfg.enabled,
            "allow_row_export": cfg.allow_row_export,
            "disabled_reason": cfg.disabled_reason,
        }
        stmt = insert(sources).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[sources.c.id],
            set_={**{k: stmt.excluded[k] for k in values if k != "id"}, "updated_at": func.now()},
        )
        conn.execute(stmt)


def sync_skills(conn: Connection, dictionary: SkillDictionary) -> dict[str, int]:
    """Upsert the dictionary into `skills`; skills no longer in the dictionary are deactivated."""
    for skill in dictionary.skills:
        stmt = insert(skills).values(
            slug=skill.slug,
            name=skill.name,
            category=skill.category,
            aliases=list(skill.aliases),
            dictionary_version=dictionary.version,
            active=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[skills.c.slug],
            set_={
                "name": stmt.excluded.name,
                "category": stmt.excluded.category,
                "aliases": stmt.excluded.aliases,
                "dictionary_version": stmt.excluded.dictionary_version,
                "active": True,
            },
        )
        conn.execute(stmt)
    slugs = [s.slug for s in dictionary.skills]
    conn.execute(update(skills).where(skills.c.slug.not_in(slugs)).values(active=False))
    return {row.slug: row.id for row in conn.execute(select(skills.c.slug, skills.c.id))}


def start_run(conn: Connection, trigger: str, dictionary_version: str) -> int:
    return int(
        conn.execute(
            insert(ingestion_runs)
            .values(trigger=trigger, skills_dictionary_version=dictionary_version)
            .returning(ingestion_runs.c.id)
        ).scalar_one()
    )


def finish_run(conn: Connection, run_id: int, values: dict[str, Any]) -> None:
    conn.execute(
        update(ingestion_runs)
        .where(ingestion_runs.c.id == run_id)
        .values(**values, finished_at=func.now())
    )


def recent_fetch_counts(conn: Connection, source_id: str, limit: int = 7) -> list[int]:
    """Record counts of the most recent complete fetches of a source (for anomaly checks)."""
    rows = conn.execute(
        text(
            """
            SELECT (details -> 'sources' -> :sid ->> 'fetched')::int AS fetched
            FROM ingestion_runs
            WHERE status IN ('succeeded', 'partial')
              AND (details -> 'sources' -> :sid ->> 'complete')::boolean IS TRUE
            ORDER BY started_at DESC
            LIMIT :limit
            """
        ),
        {"sid": source_id, "limit": limit},
    )
    return [r.fetched for r in rows if r.fetched is not None]


def existing_dedup_keys(conn: Connection, keys: Sequence[str]) -> set[str]:
    found: set[str] = set()
    for chunk in _chunks(list(keys)):
        found.update(
            conn.execute(select(jobs.c.dedup_key).where(jobs.c.dedup_key.in_(chunk))).scalars()
        )
    return found


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0
    observations: int = 0
    skill_links: int = 0
    job_ids: dict[str, int] | None = None


def upsert_jobs(
    conn: Connection,
    records: Sequence[JobRecord],
    *,
    run_id: int,
    now: datetime,
    dictionary_version: str,
    skill_ids: dict[str, int],
    retain_description_days: int,
) -> UpsertStats:
    stats = UpsertStats(job_ids={})
    assert stats.job_ids is not None
    for chunk in _chunks(list(records)):
        rows = [
            {
                "source_id": r.source_id,
                "source_job_id": r.source_job_id,
                "canonical_url": r.canonical_url,
                "dedup_key": r.dedup_key,
                "cross_source_key": r.cross_source_key,
                "title_original": r.title_original,
                "title_normalized": r.title_normalized,
                "role_category": r.role_category,
                "company": r.company,
                "location_original": r.location_original,
                "city": r.city,
                "region": r.region,
                "country": r.country,
                "work_mode": r.work_mode,
                "work_mode_basis": r.work_mode_basis,
                "employment_type": r.employment_type,
                "seniority": r.seniority,
                "salary_text": r.salary_text,
                "salary_min": r.salary_min,
                "salary_max": r.salary_max,
                "salary_currency": r.salary_currency,
                "salary_period": r.salary_period,
                "source_tags": list(r.source_tags),
                "published_at": r.published_at,
                "first_seen_at": now,
                "last_seen_at": now,
                "status": "active",
                "status_changed_at": now,
                "consecutive_misses": 0,
                "skills_dictionary_version": dictionary_version,
            }
            for r in chunk
        ]
        base = insert(jobs)
        refreshed = [
            "source_job_id",
            "canonical_url",
            "cross_source_key",
            "title_original",
            "title_normalized",
            "role_category",
            "company",
            "location_original",
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
            "source_tags",
            "skills_dictionary_version",
        ]
        upsert = base.on_conflict_do_update(
            index_elements=[jobs.c.dedup_key],
            set_={
                **{c: base.excluded[c] for c in refreshed},
                # Keep the earliest known publication date if the source drops it later.
                "published_at": func.coalesce(base.excluded.published_at, jobs.c.published_at),
                "last_seen_at": func.greatest(jobs.c.last_seen_at, base.excluded.last_seen_at),
                "status_changed_at": text(
                    "CASE WHEN jobs.status <> 'active' THEN excluded.status_changed_at "
                    "ELSE jobs.status_changed_at END"
                ),
                "status": "active",
                "consecutive_misses": 0,
                "updated_at": func.now(),
            },
        ).returning(
            jobs.c.id,
            jobs.c.dedup_key,
            text("(xmax = 0) AS inserted"),
            sort_by_parameter_order=True,
        )
        for row in conn.execute(upsert, rows):
            stats.job_ids[row.dedup_key] = row.id
            if row.inserted:
                stats.inserted += 1
            else:
                stats.updated += 1

    by_key = {r.dedup_key: r for r in records}
    ids = list(stats.job_ids.values())
    obs_date = now.date()
    obs_rows = [
        {
            "job_id": stats.job_ids[key],
            "run_id": run_id,
            "source_id": rec.source_id,
            "observation_date": obs_date,
            "observed_at": now,
            "observation_method": "feed",
            "observed_status": "active",
            "title_normalized": rec.title_normalized,
            "role_category": rec.role_category,
            "work_mode": rec.work_mode,
            "salary_min": rec.salary_min,
            "salary_max": rec.salary_max,
            "salary_currency": rec.salary_currency,
            "salary_period": rec.salary_period,
        }
        for key, rec in by_key.items()
    ]
    for chunk in _chunks(obs_rows):
        stmt = insert(job_observations)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_job_observations_job_date",
            set_={
                c: stmt.excluded[c]
                for c in (
                    "run_id",
                    "observed_at",
                    "observation_method",
                    "observed_status",
                    "title_normalized",
                    "role_category",
                    "work_mode",
                    "salary_min",
                    "salary_max",
                    "salary_currency",
                    "salary_period",
                )
            },
        )
        conn.execute(stmt, list(chunk))
        stats.observations += len(chunk)

    # Skill links for this dictionary version are replaced, so a changed description can
    # remove a skill as well as add one. Links from other versions are left untouched.
    link_rows = [
        {
            "job_id": stats.job_ids[key],
            "skill_id": skill_ids[slug],
            "dictionary_version": dictionary_version,
            "matched_in": where,
            "detected_at": now,
        }
        for key, rec in by_key.items()
        for slug, where in rec.skills.items()
        if slug in skill_ids
    ]
    for chunk in _chunks(ids):
        conn.execute(
            job_skills.delete().where(
                job_skills.c.job_id.in_(chunk),
                job_skills.c.dictionary_version == dictionary_version,
            )
        )
    for chunk in _chunks(link_rows):
        conn.execute(insert(job_skills), list(chunk))
        stats.skill_links += len(chunk)

    if retain_description_days > 0:
        purge_after = now + timedelta(days=retain_description_days)
        desc_rows = [
            {
                "job_id": stats.job_ids[key],
                "text_plain": rec.description_text[:50_000],
                "captured_at": now,
                "purge_after": purge_after,
            }
            for key, rec in by_key.items()
            if rec.description_text
        ]
        for chunk in _chunks(desc_rows):
            stmt = insert(job_descriptions)
            stmt = stmt.on_conflict_do_update(
                index_elements=[job_descriptions.c.job_id],
                set_={c: stmt.excluded[c] for c in ("text_plain", "captured_at", "purge_after")},
            )
            conn.execute(stmt, list(chunk))
    return stats


def status_check_candidates(
    conn: Connection, source_id: str, seen_keys: Sequence[str], limit: int
) -> list[tuple[int, str]]:
    """Jobs of a source absent from this fetch and not already expired, least recently
    verified first, as (job id, source-native id)."""
    rows = conn.execute(
        text(
            """
            SELECT id, source_job_id FROM jobs
            WHERE source_id = :sid AND status <> 'expired' AND source_job_id IS NOT NULL
              AND NOT (dedup_key = ANY(:seen))
            ORDER BY COALESCE(last_verified_active_at, last_seen_at) ASC, id
            LIMIT :limit
            """
        ),
        {"sid": source_id, "seen": list(seen_keys), "limit": limit},
    )
    return [(r.id, r.source_job_id) for r in rows]


def apply_status_results(
    conn: Connection,
    *,
    source_id: str,
    run_id: int,
    now: datetime,
    results: dict[int, str],
) -> tuple[int, int]:
    """Apply explicit source status reports. Returns (expired, verified_active)."""
    closed = [jid for jid, s in results.items() if s == "closed"]
    active = [jid for jid, s in results.items() if s == "active"]
    expired = 0
    if closed:
        expired = conn.execute(
            text(
                """
                UPDATE jobs SET status = 'expired', status_changed_at = :now,
                       source_reported_closed_at = COALESCE(source_reported_closed_at, :now),
                       updated_at = now()
                WHERE id = ANY(:ids) AND status <> 'expired'
                """
            ),
            {"ids": closed, "now": now},
        ).rowcount
    if active:
        conn.execute(
            text(
                """
                UPDATE jobs SET last_verified_active_at = :now, consecutive_misses = 0,
                       status_changed_at = CASE WHEN status <> 'active' THEN :now
                                                ELSE status_changed_at END,
                       status = 'active', updated_at = now()
                WHERE id = ANY(:ids)
                """
            ),
            {"ids": active, "now": now},
        )
    checked = closed + active
    if checked:
        conn.execute(
            text(
                """
                INSERT INTO job_observations (job_id, run_id, source_id, observation_date,
                    observed_at, observation_method, observed_status, title_normalized,
                    role_category, work_mode, salary_min, salary_max, salary_currency,
                    salary_period)
                SELECT id, :run_id, source_id, :obs_date, :now, 'status_check', status,
                       title_normalized, role_category, work_mode, salary_min, salary_max,
                       salary_currency, salary_period
                FROM jobs WHERE id = ANY(:ids)
                ON CONFLICT ON CONSTRAINT uq_job_observations_job_date DO NOTHING
                """
            ),
            {"ids": checked, "run_id": run_id, "obs_date": now.date(), "now": now},
        )
    return expired, len(active)


def record_misses(
    conn: Connection,
    *,
    source_id: str,
    seen_keys: Sequence[str],
    exclude_ids: Sequence[int],
    threshold: int,
    now: datetime,
) -> int:
    """Only called after a COMPLETE, non-anomalous fetch. Increments the miss counter of jobs
    absent from the feed and marks them 'unconfirmed' once the threshold is reached.
    Nothing is deleted and 'unconfirmed' is never treated as a verified closure."""
    conn.execute(
        text(
            """
            UPDATE jobs SET consecutive_misses = consecutive_misses + 1, updated_at = now()
            WHERE source_id = :sid AND status IN ('active', 'unconfirmed')
              AND NOT (dedup_key = ANY(:seen)) AND NOT (id = ANY(:skip))
            """
        ),
        {"sid": source_id, "seen": list(seen_keys), "skip": list(exclude_ids)},
    )
    return conn.execute(
        text(
            """
            UPDATE jobs SET status = 'unconfirmed', status_changed_at = :now, updated_at = now()
            WHERE source_id = :sid AND status = 'active' AND consecutive_misses >= :threshold
            """
        ),
        {"sid": source_id, "threshold": threshold, "now": now},
    ).rowcount


def update_source_state(
    conn: Connection,
    source_id: str,
    *,
    attempted_at: datetime,
    success: bool,
    complete: bool | None,
    record_count: int | None,
    error_summary: str | None,
) -> None:
    values: dict[str, Any] = {"last_attempt_at": attempted_at, "updated_at": func.now()}
    if success:
        values.update(
            last_success_at=attempted_at,
            last_fetch_complete=complete,
            last_record_count=record_count,
        )
    if error_summary:
        values.update(last_error_at=attempted_at, last_error_summary=error_summary)
    conn.execute(update(sources).where(sources.c.id == source_id).values(**values))


def record_quality(
    conn: Connection,
    run_id: int,
    source_id: str | None,
    check_name: str,
    outcome: str,
    failed_count: int = 0,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        insert(data_quality_results).values(
            run_id=run_id,
            source_id=source_id,
            check_name=check_name,
            outcome=outcome,
            failed_count=failed_count,
            details=details or {},
        )
    )


def post_write_integrity(conn: Connection, run_id: int, obs_date: Any) -> dict[str, int]:
    """Database-side checks after writes (should all be zero)."""
    row = conn.execute(
        text(
            """
            SELECT
              (SELECT count(*) FROM (SELECT job_id, observation_date FROM job_observations
                 GROUP BY 1, 2 HAVING count(*) > 1) d) AS duplicate_snapshots,
              (SELECT count(*) FROM jobs j WHERE j.status = 'active'
                 AND (j.last_seen_at AT TIME ZONE 'UTC')::date = :obs_date
                 AND NOT EXISTS (SELECT 1 FROM job_observations o
                                 WHERE o.job_id = j.id AND o.observation_date = :obs_date))
                 AS seen_without_observation,
              (SELECT count(*) FROM jobs WHERE first_seen_at > last_seen_at) AS bad_seen_order,
              (SELECT count(*) FROM jobs WHERE salary_min > salary_max) AS bad_salary_ranges
            """
        ),
        {"obs_date": obs_date},
    ).one()
    return dict(row._mapping)


def purge_descriptions(conn: Connection, now: datetime) -> int:
    return conn.execute(
        job_descriptions.delete().where(job_descriptions.c.purge_after < now)
    ).rowcount
