"""The one ingestion pipeline. The CLI, GitHub Actions (scheduled and manual) and the
integration tests all call `run_pipeline`; there is no other copy of this logic.

Per enabled source:
  fetch -> parse -> normalize -> validate (row) -> deduplicate -> validate (batch)
  -> anomaly check -> [status checks] -> upsert jobs / observations / skills (one transaction)
  -> lifecycle (only after complete fetches) -> data-quality results -> source state.
A failure in one source is recorded and does not discard other sources' data.
"""

import logging
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine

from backend.core.logging import log_event, safe_error_summary
from backend.ingestion import persistence as db
from backend.ingestion.config import SourceConfig, load_source_configs
from backend.ingestion.skills.extractor import SkillDictionary, load_skill_dictionary
from backend.ingestion.sources import build_adapter
from backend.ingestion.sources.base import FetchResult, ParseError, SourceAdapter
from backend.ingestion.transformations.normalize import InvalidRecord, normalize_job
from backend.ingestion.transformations.roles import RoleRules, load_role_rules
from backend.ingestion.validation.batch import count_anomaly, validate_batch
from backend.ingestion.validation.contracts import JobRecord

logger = logging.getLogger(__name__)
TRIGGERS = ("cli", "schedule", "manual", "test")


@dataclass
class SourceStats:
    source_id: str
    success: bool = False
    complete: bool = False
    fetched: int = 0
    valid: int = 0
    invalid: int = 0
    out_of_scope: int = 0
    duplicates: int = 0
    inserted: int = 0
    updated: int = 0
    would_insert: int = 0
    would_update: int = 0
    observations: int = 0
    skill_links: int = 0
    status_checks: int = 0
    expired: int = 0
    unconfirmed: int = 0
    requests: int = 0
    duration_s: float = 0.0
    lifecycle_applied: bool = False
    quality_failed: bool = False
    anomaly: str | None = None
    errors: list[str] = field(default_factory=list)
    invalid_reasons: dict[str, int] = field(default_factory=dict)
    salary_issues: dict[str, int] = field(default_factory=dict)


@dataclass
class RunSummary:
    trigger: str
    dry_run: bool
    started_at: datetime
    run_id: int | None = None
    finished_at: datetime | None = None
    status: str = "running"
    dictionary_version: str = ""
    sources: dict[str, SourceStats] = field(default_factory=dict)

    def total(self, name: str) -> int:
        return sum(int(getattr(s, name)) for s in self.sources.values())

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "failed" else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "dry_run": self.dry_run,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "skills_dictionary_version": self.dictionary_version,
            "totals": {
                k: self.total(k)
                for k in (
                    "fetched",
                    "valid",
                    "invalid",
                    "out_of_scope",
                    "duplicates",
                    "inserted",
                    "updated",
                    "would_insert",
                    "would_update",
                    "observations",
                    "skill_links",
                    "status_checks",
                    "expired",
                    "unconfirmed",
                )
            },
            "sources": {sid: asdict(s) for sid, s in self.sources.items()},
        }


@dataclass
class PreparedBatch:
    records: list[JobRecord]
    stats: SourceStats


def prepare_records(
    adapter: SourceAdapter,
    fetched: FetchResult,
    *,
    stats: SourceStats,
    skills: SkillDictionary,
    roles: RoleRules,
) -> list[JobRecord]:
    """Parse, normalize, validate and deduplicate one source's raw records (no I/O)."""
    invalid: Counter[str] = Counter()
    salary_issues: Counter[str] = Counter()
    unique: dict[str, JobRecord] = {}
    for raw in fetched.records:
        try:
            parsed = adapter.parse(raw)
            outcome = normalize_job(
                parsed,
                source=adapter.config,
                observed_at=fetched.fetched_at,
                skills=skills,
                roles=roles,
            )
        except (InvalidRecord, ParseError) as exc:
            invalid[getattr(exc, "reason", str(exc))[:120]] += 1
            continue
        if outcome.out_of_scope:
            stats.out_of_scope += 1
            continue
        assert outcome.record is not None
        if outcome.salary_issue and outcome.salary_issue != "unparseable":
            salary_issues[outcome.salary_issue] += 1
        if outcome.record.dedup_key in unique:
            stats.duplicates += 1  # first occurrence wins (deterministic: feed order)
            continue
        unique[outcome.record.dedup_key] = outcome.record
    stats.invalid = sum(invalid.values())
    stats.invalid_reasons = dict(invalid.most_common(20))
    stats.salary_issues = dict(salary_issues)
    stats.valid = len(unique)
    in_scope = stats.fetched - stats.out_of_scope if stats.fetched else len(fetched.records)
    stats.quality_failed = _quality_outcome(stats.invalid, in_scope) == "fail"
    return list(unique.values())


def _quality_outcome(bad: int, total: int, warn_ratio: float = 0.0, fail_ratio: float = 0.1) -> str:
    if bad == 0:
        return "pass"
    if total and bad / total > fail_ratio:
        return "fail"
    return "warn" if bad / max(total, 1) >= warn_ratio else "pass"


def _process_source(
    adapter: SourceAdapter,
    engine: Engine | None,
    summary: RunSummary,
    *,
    skills: SkillDictionary,
    roles: RoleRules,
    skill_ids: dict[str, int],
    now_fn: Callable[[], datetime],
) -> SourceStats:
    cfg = adapter.config
    stats = SourceStats(source_id=cfg.id)
    started = time.monotonic()
    attempted_at = now_fn()
    try:
        fetched = adapter.fetch()
    except Exception as exc:
        stats.errors.append(safe_error_summary(exc))
        stats.requests = adapter.request_count
        stats.duration_s = round(time.monotonic() - started, 2)
        if engine is not None and not summary.dry_run and summary.run_id is not None:
            with engine.begin() as conn:
                db.update_source_state(
                    conn,
                    cfg.id,
                    attempted_at=attempted_at,
                    success=False,
                    complete=None,
                    record_count=None,
                    error_summary=stats.errors[0],
                )
                db.record_quality(
                    conn,
                    summary.run_id,
                    cfg.id,
                    "fetch_completeness",
                    "fail",
                    1,
                    {"error": stats.errors[0]},
                )
        return stats

    stats.fetched = len(fetched.records)
    stats.complete = fetched.complete
    stats.errors.extend(fetched.errors)
    records = prepare_records(adapter, fetched, stats=stats, skills=skills, roles=roles)
    batch = validate_batch(records)
    if not batch.passed:
        stats.errors.append("batch validation failed: " + "; ".join(batch.failures)[:250])

    history: list[int] = []
    existing: set[str] = set()
    if engine is not None:
        with engine.connect() as conn:
            history = db.recent_fetch_counts(conn, cfg.id)
            if summary.dry_run:
                existing = db.existing_dedup_keys(conn, [r.dedup_key for r in records])
    stats.anomaly = count_anomaly(stats.fetched, history)
    # Absence-based lifecycle changes need a complete, non-anomalous, non-empty fetch: an empty
    # or truncated response must never make existing listings look like they disappeared.
    lifecycle_ok = stats.complete and stats.anomaly is None and batch.passed and stats.valid > 0

    if summary.dry_run or engine is None:
        stats.would_update = len(existing)
        stats.would_insert = len(records) - len(existing)
        stats.success = batch.passed
        stats.requests = adapter.request_count
        stats.duration_s = round(time.monotonic() - started, 2)
        return stats

    assert summary.run_id is not None
    run_id = summary.run_id
    seen_keys = [r.dedup_key for r in records]

    # Explicit closure checks happen over the network BEFORE the write transaction opens.
    status_results: dict[int, str] = {}
    if batch.passed and cfg.status_check_enabled:
        limit = int(cfg.options.get("status_check_max_ids", 500))
        with engine.connect() as conn:
            candidates = db.status_check_candidates(conn, cfg.id, seen_keys, limit)
        if candidates:
            try:
                reported = adapter.check_status([sid for _, sid in candidates])
                status_results = {jid: reported[sid] for jid, sid in candidates if sid in reported}
                stats.status_checks = len(candidates)
            except Exception as exc:
                stats.errors.append("status check: " + safe_error_summary(exc))

    now = fetched.fetched_at
    try:
        with engine.begin() as conn:
            if batch.passed and records:
                result = db.upsert_jobs(
                    conn,
                    records,
                    run_id=run_id,
                    now=now,
                    dictionary_version=skills.version,
                    skill_ids=skill_ids,
                    retain_description_days=cfg.retain_description_days,
                )
                stats.inserted, stats.updated = result.inserted, result.updated
                stats.observations, stats.skill_links = result.observations, result.skill_links
            verified: list[int] = []
            if status_results:
                stats.expired, _ = db.apply_status_results(
                    conn, source_id=cfg.id, run_id=run_id, now=now, results=status_results
                )
                verified = [j for j, s in status_results.items() if s in ("active", "closed")]
            if lifecycle_ok:
                stats.unconfirmed = db.record_misses(
                    conn,
                    source_id=cfg.id,
                    seen_keys=seen_keys,
                    exclude_ids=verified,
                    threshold=cfg.unconfirmed_after_misses,
                    now=now,
                )
                stats.lifecycle_applied = True
            _record_source_quality(conn, run_id, stats, batch.failures)
            stats.success = batch.passed
            db.update_source_state(
                conn,
                cfg.id,
                attempted_at=attempted_at,
                success=stats.success,
                complete=stats.complete,
                record_count=stats.fetched,
                error_summary="; ".join(stats.errors)[:300] or None,
            )
    except Exception as exc:
        stats.success = False
        stats.inserted = stats.updated = stats.observations = stats.skill_links = 0
        stats.expired = stats.unconfirmed = 0
        stats.errors.append("database write: " + safe_error_summary(exc))
        with engine.begin() as conn:
            db.update_source_state(
                conn,
                cfg.id,
                attempted_at=attempted_at,
                success=False,
                complete=None,
                record_count=None,
                error_summary=stats.errors[-1],
            )
    stats.requests = adapter.request_count
    stats.duration_s = round(time.monotonic() - started, 2)
    return stats


def _record_source_quality(
    conn: Any, run_id: int, stats: SourceStats, batch_failures: list[str]
) -> None:
    sid = stats.source_id
    db.record_quality(
        conn,
        run_id,
        sid,
        "fetch_completeness",
        "pass" if stats.complete else "warn",
        0 if stats.complete else 1,
        {"errors": stats.errors[:5]},
    )
    db.record_quality(
        conn,
        run_id,
        sid,
        "required_fields_and_formats",
        _quality_outcome(stats.invalid, stats.fetched - stats.out_of_scope),
        stats.invalid,
        {"reasons": stats.invalid_reasons},
    )
    db.record_quality(
        conn,
        run_id,
        sid,
        "duplicate_listings",
        "warn" if stats.duplicates else "pass",
        stats.duplicates,
        {"resolution": "first occurrence kept"},
    )
    salary_bad = sum(stats.salary_issues.values())
    db.record_quality(
        conn,
        run_id,
        sid,
        "salary_consistency",
        "warn" if salary_bad else "pass",
        salary_bad,
        {"issues": stats.salary_issues},
    )
    db.record_quality(
        conn,
        run_id,
        sid,
        "record_count_anomaly",
        "warn" if stats.anomaly else "pass",
        1 if stats.anomaly else 0,
        {"message": stats.anomaly},
    )
    db.record_quality(
        conn,
        run_id,
        sid,
        "batch_schema",
        "fail" if batch_failures else "pass",
        len(batch_failures),
        {"failures": batch_failures[:10]},
    )


def _overall_status(stats: Sequence[SourceStats]) -> str:
    if not stats or not any(s.success for s in stats):
        return "failed"
    if all(s.success and s.complete and not s.anomaly and not s.quality_failed for s in stats):
        return "succeeded"
    return "partial"


def run_pipeline(
    *,
    engine: Engine | None,
    trigger: str = "cli",
    dry_run: bool = False,
    source_ids: Sequence[str] | None = None,
    configs: dict[str, SourceConfig] | None = None,
    adapters: dict[str, SourceAdapter] | None = None,
    skills: SkillDictionary | None = None,
    roles: RoleRules | None = None,
    now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> RunSummary:
    if trigger not in TRIGGERS:
        raise ValueError(f"trigger must be one of {TRIGGERS}")
    if engine is None and not dry_run:
        raise ValueError("a database engine is required unless dry_run=True")
    configs = configs or load_source_configs()
    skills = skills or load_skill_dictionary()
    roles = roles or load_role_rules()
    summary = RunSummary(
        trigger=trigger, dry_run=dry_run, started_at=now_fn(), dictionary_version=skills.version
    )

    selected = [c for c in configs.values() if c.enabled]
    if source_ids:
        unknown = set(source_ids) - {c.id for c in selected}
        if unknown:
            raise ValueError(f"unknown or disabled sources: {sorted(unknown)}")
        selected = [c for c in selected if c.id in source_ids]
    adapters = adapters or {}

    skill_ids: dict[str, int] = {}
    if engine is not None and not dry_run:
        with engine.begin() as conn:
            db.sync_sources(conn, list(configs.values()))
            skill_ids = db.sync_skills(conn, skills)
            summary.run_id = db.start_run(conn, trigger, skills.version)
    log_event(
        logger,
        "ingestion run started",
        run_id=summary.run_id,
        trigger=trigger,
        dry_run=dry_run,
        sources=[c.id for c in selected],
    )

    for cfg in selected:
        adapter = adapters.get(cfg.id) or build_adapter(cfg)
        stats = _process_source(
            adapter, engine, summary, skills=skills, roles=roles, skill_ids=skill_ids, now_fn=now_fn
        )
        summary.sources[cfg.id] = stats
        log_event(
            logger,
            "source processed",
            source=cfg.id,
            success=stats.success,
            complete=stats.complete,
            fetched=stats.fetched,
            valid=stats.valid,
            invalid=stats.invalid,
            inserted=stats.inserted,
            updated=stats.updated,
            errors=stats.errors[:3],
        )

    summary.status = _overall_status(list(summary.sources.values()))
    summary.finished_at = now_fn()
    if engine is not None and not dry_run and summary.run_id is not None:
        with engine.begin() as conn:
            integrity = db.post_write_integrity(conn, summary.run_id, summary.started_at.date())
            bad = sum(integrity.values())
            db.record_quality(
                conn,
                summary.run_id,
                None,
                "post_write_integrity",
                "fail" if bad else "pass",
                bad,
                integrity,
            )
            purged = db.purge_descriptions(conn, summary.finished_at)
            errors = [f"{s.source_id}: {e}" for s in summary.sources.values() for e in s.errors]
            db.finish_run(
                conn,
                summary.run_id,
                {
                    "status": summary.status,
                    "sources_attempted": len(summary.sources),
                    "sources_succeeded": sum(1 for s in summary.sources.values() if s.success),
                    "records_fetched": summary.total("fetched"),
                    "records_valid": summary.total("valid"),
                    "records_invalid": summary.total("invalid"),
                    "records_out_of_scope": summary.total("out_of_scope"),
                    "duplicates": summary.total("duplicates"),
                    "jobs_inserted": summary.total("inserted"),
                    "jobs_updated": summary.total("updated"),
                    "observations_written": summary.total("observations"),
                    "skill_links_written": summary.total("skill_links"),
                    "status_checks": summary.total("status_checks"),
                    "jobs_marked_expired": summary.total("expired"),
                    "jobs_marked_unconfirmed": summary.total("unconfirmed"),
                    "error_count": len(errors),
                    "error_summary": " | ".join(errors)[:1000] or None,
                    "details": {
                        "sources": {
                            sid: {
                                "fetched": s.fetched,
                                "complete": s.complete,
                                "success": s.success,
                                "valid": s.valid,
                                "invalid": s.invalid,
                                "requests": s.requests,
                                "duration_s": s.duration_s,
                                "anomaly": s.anomaly,
                                "lifecycle_applied": s.lifecycle_applied,
                            }
                            for sid, s in summary.sources.items()
                        },
                        "integrity": integrity,
                        "descriptions_purged": purged,
                    },
                },
            )
    log_event(logger, "ingestion run finished", run_id=summary.run_id, status=summary.status)
    return summary
