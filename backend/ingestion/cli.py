"""Command-line entry point.

    uv run python -m backend.ingestion.cli run [--dry-run] [--source jobicy] [--trigger cli]
    uv run python -m backend.ingestion.cli check-sources
    uv run python -m backend.ingestion.cli reprocess-skills

Exit codes: 0 = succeeded or partial (some source degraded; details in the summary),
1 = failed (no source succeeded), 2 = configuration error.
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from backend.core.config import get_settings
from backend.core.db import make_engine
from backend.core.logging import configure_logging, safe_error_summary
from backend.ingestion.config import load_source_configs
from backend.ingestion.orchestrator import RunSummary, run_pipeline
from backend.ingestion.sources import build_adapter


def _markdown_summary(summary: RunSummary) -> str:
    data = summary.to_dict()
    lines = [
        f"## Ingestion run {'(dry run)' if summary.dry_run else f'#{summary.run_id}'}",
        "",
        f"- **Status:** {summary.status}",
        f"- **Trigger:** {summary.trigger}",
        f"- **Skill dictionary:** {summary.dictionary_version}",
        "",
        "| Source | OK | Complete | Fetched | Valid | Invalid | Out of scope | Dupes | "
        "Inserted | Updated | Observations | Expired | Unconfirmed |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for sid, s in data["sources"].items():
        ins = s["would_insert"] if summary.dry_run else s["inserted"]
        upd = s["would_update"] if summary.dry_run else s["updated"]
        lines.append(
            f"| {sid} | {'yes' if s['success'] else 'NO'} | {'yes' if s['complete'] else 'no'} "
            f"| {s['fetched']} | {s['valid']} | {s['invalid']} | {s['out_of_scope']} "
            f"| {s['duplicates']} | {ins} | {upd} | {s['observations']} | {s['expired']} "
            f"| {s['unconfirmed']} |"
        )
    errors = [f"- `{sid}`: {e}" for sid, s in data["sources"].items() for e in s["errors"]]
    if errors:
        lines += ["", "### Source errors", *errors]
    return "\n".join(lines) + "\n"


def cmd_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = None
    if settings.ingest_database_url:
        engine = make_engine(settings.ingest_database_url)
    elif not args.dry_run:
        print(
            "INGEST_DATABASE_URL is not set (use --dry-run to test without a database).",
            file=sys.stderr,
        )
        return 2
    summary = run_pipeline(
        engine=engine,
        trigger=args.trigger,
        dry_run=args.dry_run,
        source_ids=args.source or None,
    )
    print(json.dumps(summary.to_dict(), indent=2, default=str))
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with Path(step_summary).open("a", encoding="utf-8") as fh:
            fh.write(_markdown_summary(summary))
    if summary.status == "partial":
        print("::warning::Ingestion finished with status 'partial' (see summary).")
    elif summary.status == "failed":
        print("::error::Ingestion failed: no source succeeded.")
    return summary.exit_code


def cmd_check_sources(_: argparse.Namespace) -> int:
    ok = True
    for cfg in load_source_configs().values():
        if not cfg.enabled:
            print(f"{cfg.id}: disabled ({cfg.disabled_reason or 'no reason recorded'})")
            continue
        try:
            result = build_adapter(cfg).health_check()
            print(f"{cfg.id}: ok {json.dumps(result, default=str)}")
        except Exception as exc:
            ok = False
            print(f"{cfg.id}: FAILED {safe_error_summary(exc)}")
    return 0 if ok else 1


def cmd_reprocess_skills(_: argparse.Namespace) -> int:
    from backend.ingestion.reprocess import reprocess_skills

    settings = get_settings()
    if not settings.ingest_database_url:
        print("INGEST_DATABASE_URL is not set.", file=sys.stderr)
        return 2
    result = reprocess_skills(make_engine(settings.ingest_database_url), datetime.now(UTC))
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="backend.ingestion.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the ingestion pipeline")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch, validate and report proposed changes without writing",
    )
    run.add_argument("--source", action="append", help="limit to a source id (repeatable)")
    run.add_argument("--trigger", default="cli", choices=["cli", "schedule", "manual"])
    run.set_defaults(func=cmd_run)
    sub.add_parser("check-sources", help="health-check enabled sources").set_defaults(
        func=cmd_check_sources
    )
    sub.add_parser(
        "reprocess-skills",
        help="re-run skill extraction for jobs whose description is still retained",
    ).set_defaults(func=cmd_reprocess_skills)
    args = parser.parse_args(argv)
    configure_logging(get_settings().log_level)
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
