# Operations runbook

## Daily operation (normal)
1. `Daily ingestion` workflow runs at ~03:17 UTC (GitHub may delay it).
2. Check: Actions → *Daily ingestion* → latest run → job summary table (per-source counts, errors).
3. Check the dashboard *Data Sources* page: source health, last runs, data-quality results.
4. *Production smoke test* runs at ~04:47 UTC once the repository variables `DASHBOARD_URL` and
   `API_URL` are set.

Status meanings: `succeeded` (all sources complete), `partial` (a source failed, was incomplete,
anomalous, or had > 10 % invalid records — exit code 0 with a warning annotation), `failed` (no source
succeeded — exit code 1; the workflow run fails and GitHub notifies according to the owner's notification settings).

## Manual run
- GitHub: Actions → *Daily ingestion* → *Run workflow* (optionally tick *dry run*).
- CLI: `gh workflow run ingest.yml -R parammeet83/job-market-intelligence [-f dry_run=true]`
- Local against production is possible with `INGEST_DATABASE_URL` in `.env`, but prefer the workflow.

Reruns are safe (idempotent). Concurrency is limited to one ingestion at a time.

## Common problems

| Symptom | Likely cause | Action |
|---|---|---|
| Source `failing`, error `HTTP 429` | rate limited | Nothing; the next daily run retries. Do not increase frequency. |
| Source `failing`, `HTTP 403`/`404` | API changed or access revoked | Check the source's docs/terms; disable the source in `config/sources.toml` if access is withdrawn. |
| `record_count_anomaly` warning | feed shrank suddenly | Usually transient; lifecycle updates were skipped automatically. Investigate if it persists. |
| `required_fields_and_formats` fail | payload format changed | Inspect `details.reasons` in `data_quality_results`; update the adapter + fixtures. |
| Workflow error "INGEST_DATABASE_URL is not configured" | missing secret | Add the repository secret (see DEPLOYMENT.md). |
| DB connection timeouts | Neon compute waking from scale-to-zero, or Neon quota reached | Retry; check Neon console usage. On Free, exhausted compute suspends until the next month — no charges. |
| Dashboard shows "Data could not be loaded" | API down or DB unreachable | `curl $API/api/v1/health`; check Vercel function logs. |
| Dashboard freshness "Stale" | schedule delayed/disabled | Check Actions; scheduled workflows are disabled after 60 days without repository activity — re-enable in the Actions tab. |

## Schema changes
1. Change `backend/app/models`, create a migration: `uv run alembic revision --autogenerate -m "..."`.
2. Review the generated file by hand; never drop tables/columns that hold history without a plan.
3. CI runs `alembic upgrade head` + `alembic check` on a fresh PostgreSQL.
4. After merge: Actions → *Database migration (manual)* → type `migrate`. The run aborts if the
   connected database name differs from `EXPECTED_DATABASE_NAME`.
5. If new tables need grants, tick *reprovision roles* (requires the role password secrets) or
   run `python -m backend.ops.roles provision` locally with `MIGRATION_DATABASE_URL`.

## Skill dictionary changes
1. Edit `config/skills.toml` and bump `version`.
2. Add tests for new aliases and false positives.
3. After deploy, the next run extracts with the new version; to update retained jobs immediately:
   `uv run python -m backend.ingestion.cli reprocess-skills` (writer credentials).

## Credential rotation
1. Locally with `MIGRATION_DATABASE_URL` in `.env`:
   `uv run python -m backend.ops.roles provision --write-env .env` (new random passwords; never printed).
2. Update secrets without displaying them, e.g.
   `grep '^INGEST_DATABASE_URL=' .env | cut -d= -f2- | gh secret set INGEST_DATABASE_URL -R parammeet83/job-market-intelligence`
   and for Vercel `vercel env rm API_DATABASE_URL production` then pipe the new value into `vercel env add API_DATABASE_URL production`.
3. Redeploy the API (`vercel deploy --prod` from the repo root) and run `python -m backend.ops.roles verify`.
4. Owner password: reset in the Neon console, then update the `MIGRATION_DATABASE_URL` secret.

## Incident: suspected credential leak
1. Rotate the affected role immediately (above). 2. Check Neon for unexpected activity.
3. Remove the secret from Git history only with the owner's approval (force-push rules apply).

## Free-tier guardrails
- Neon Free: if compute or storage limits are reached the project is suspended/restricted until the
  next period — there is no automatic charge. Do not add a payment method.
- Vercel Hobby: personal, non-commercial use. Do not enable paid add-ons.
- GitHub Actions: public repositories use standard runners free of charge.
