# Tasks

`[x]` = done and verified as described · `[ ]` = open. Production items are ticked only after they
were checked against the live system.

## Phase 1 — Inspection & planning
- [x] Verify project path, branch `main`, remote `origin`, Git identity, empty remote
- [x] Check Python, uv, Node, npm, gh, Vercel CLI; note Neon CLI/MCP not authenticated
- [x] Review Jobicy, Remote OK, Arbeitnow, Remotive terms, docs and robots.txt
- [x] Check Neon Free, Vercel FastAPI/Python runtime, GitHub schedule docs
- [x] Write implementation plan and risks

## Phase 2 — Foundation
- [x] `pyproject.toml` + `uv.lock` (runtime / ingestion / dev groups), `.python-version`
- [x] Vite React TS app + `package-lock.json`; Tailwind 4; Recharts; React Router
- [x] `.gitignore`, `.env.example`, `frontend/.env.example`
- [x] Alembic config with database-name guard; migrations 0001 (schema) and 0002 (views)
- [x] ruff, mypy, pytest, oxlint, tsc, vitest, Playwright configured

## Phase 3 — Pipeline
- [x] Source config (TOML) with enable flags, export permission, retention, host allow-list
- [x] HTTP client: timeouts, bounded retries, backoff, Retry-After, spacing, allow-list, redirect check
- [x] Jobicy adapter (industries, cursor paging, status API) and Remote OK adapter
- [x] Title, role, location, work-mode, employment, seniority, salary normalization
- [x] Versioned skill dictionary + bounded matcher; re-processing command
- [x] Pydantic contract, Pandera batch checks, anomaly check, DQ results
- [x] Deterministic dedup; idempotent upserts; daily observations; lifecycle rules
- [x] CLI `run` / `--dry-run` / `--source` / `check-sources` / `reprocess-skills`; GitHub step summary
- [x] Real data loaded into local dev DB; second run idempotent

## Phase 4 — SQL analytics
- [x] Six views; 22 parameterised analytics queries with documented denominators
- [x] Example SQL for BI users (validated against the dev DB)

## Phase 5 — API
- [x] FastAPI `/api/v1` read-only endpoints, OpenAPI at `/api/docs`
- [x] Pagination limits, validated filters, safe errors, structured logs, CORS
- [x] CSV exports (permitted sources only for row-level data, formula-injection safe)
- [x] Role provisioning + 16-check privilege verification

## Phase 6 — Dashboard
- [x] Layout + navigation (desktop sidebar, mobile menu), skip link
- [x] Overview, Job Listings, Skill Intelligence, Salary Insights, Locations & Roles, Data Sources, Methodology
- [x] URL-synced filters; loading / empty / error+retry states; table view per chart; small-sample flags
- [x] Validated chart palette; screenshots reviewed at desktop and phone sizes

## Phase 7 — GitHub Actions
- [x] `ci.yml`, `ingest.yml`, `migrate.yml`, `smoke.yml` written, SHA-pinned, least privilege
- [x] First CI run green on GitHub (run 40830848766; the first run failed only because gitleaks-action cannot scan a root commit — replaced by the gitleaks binary)
- [x] Repository secrets configured (`INGEST_DATABASE_URL`; production environment: `MIGRATION_DATABASE_URL`, `EXPECTED_DATABASE_NAME`)
- [x] Manual ingestion workflow run succeeded (run 40835215566: 380 listings inserted)
- [ ] Scheduled ingestion observed running

## Phase 8 — Deployment
- [x] Neon project `jobmarket-pulse` created on the Free plan (owner action)
- [x] Migrations applied; roles provisioned; `roles verify` 16/16 on production
- [x] API deployed to Vercel; `/api/v1/health` reports database ok; `/api/docs` reachable
- [x] Dashboard deployed to Vercel; CORS restricted to its origin
- [x] Live data visible; Playwright 18/18 against production from this machine (desktop + phone)
- [x] Production smoke workflow green on GitHub (run 40836104559: 18 passed)

## Phase 9 — QA
- [x] Backend: 160 tests passed locally (unit + PostgreSQL integration), ruff, mypy, `alembic check`
- [x] Frontend: 22 tests, lint, typecheck, build; e2e 18/18 against local stack
- [x] Secret scan (gitleaks 8.30.1) clean locally (full history + every staged commit) and in CI

## Phase 10 — Delivery
- [x] Reviewed commits pushed to `origin/main` with the owner's Git identity, no co-author trailers
- [x] README updated with verified live URLs and results only
