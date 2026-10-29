# Testing

Four layers, kept separate in reporting: **local automated tests**, **CI**, **end-to-end against a
running stack**, and **production smoke checks**. A passing layer is not evidence for another.

## Commands

```bash
# Backend: lint, format, types
uv run ruff check backend migrations
uv run ruff format --check backend migrations
uv run mypy

# Backend tests (unit always; integration when TEST_DATABASE_URL is set)
uv run pytest -q --cov

# Migrations: apply to an empty DB and compare with the models
uv run alembic -x url=$TEST_DATABASE_URL upgrade head
uv run alembic -x url=$TEST_DATABASE_URL check

# Frontend
cd frontend
npm run lint && npm run typecheck && npm test && npm run build

# End-to-end (Playwright, desktop + Pixel 7 viewports)
npx playwright install chromium
E2E_BASE_URL=http://localhost:4173 npx playwright test          # local: vite preview + uvicorn
E2E_BASE_URL=https://<dashboard> E2E_API_URL=https://<api> npx playwright test   # production
```

`TEST_DATABASE_URL` must point to a **disposable** database whose name contains `test`; the
integration fixtures drop and recreate its `public` schema, run all migrations, and create test-only
roles (`jmp_test_api_ro`, `jmp_test_ingest`). The fixture refuses any database whose name lacks
`test`. Production is never used for tests.

## What is covered

### Backend unit tests (`backend/tests/unit`, no database)
- Title normalization and seniority; role classification order.
- Location normalization (countries, US/Indian states, regions, multi-country strings), work mode.
- Salary parsing: symbols, ISO codes, `k`/`LPA`/lakh grouping, periods, ambiguity, missing ≠ 0,
  inconsistent ranges rejected, currency/period normalization.
- Skill extraction: 24 positive cases, 12 false-positive cases (`R&D`, `React`, `GitHub`,
  `JavaScript`→Java, `PySpark`→Spark, "excel at"), determinism, dictionary validation.
- Canonical URLs, dedup key priority, cross-source key.
- HTTP client: host allow-list, https only, retries with backoff, `Retry-After`, give-up on long
  waits, bounded attempts, no retry on 4xx, redirect to foreign host refused, request spacing.
- Adapters with synthetic fixtures: pagination, partial failure, status batching, legal-notice row,
  scope filter, unexpected payloads.
- Validation: invalid records with safe reasons, duplicates, future dates, Pandera batch checks,
  count anomaly, overall run status, log redaction.

### Backend integration tests (`backend/tests/integration`, PostgreSQL)
- Schema + views created by migrations; DB constraints reject bad data (7 cases).
- End-to-end pipeline and **idempotency** (3 identical runs → no new rows).
- New day → new observations, history kept.
- Partial source failure keeps other source's data; failing source never marks jobs missing.
- Incomplete fetch, empty feed, count anomaly → no absence inference.
- Absence after two complete fetches → `unconfirmed`; reappearance → `active`.
- Status API `closed` → `expired` with a `status_check` observation.
- Dry run writes nothing and reports would-insert/would-update.
- High invalid ratio → run `partial`, DQ `fail` with reasons.
- Skill re-processing with a new dictionary version.
- **Role privileges**: 16 checks (API role cannot insert/update/delete/DDL even when overriding
  read-only mode, cannot read descriptions; ingest role cannot delete jobs/observations, truncate,
  create or drop).
- API through the read-only role: health, summary vs SQL, skill-share denominator, trends,
  filters/pagination/search escaping/sorting, job detail, salary groups never mixing currencies,
  roles/locations/lifecycle/sources/runs/DQ, CSV permissions, 405 for writes, empty database.

### Frontend (`frontend/src/**/*.test.ts(x)`, Vitest + Testing Library)
- Formatting (unknown ≠ 0, percentages, salaries per currency/period), URL building, transforms
  (top-N folding preserves totals, trend pivot, salary groups, work-mode shares).
- App: loading → KPIs from API, honest empty state, error + retry, GET-only, axe accessibility scan
  (colour contrast checked separately), navigation keeps filters, 404 page, job pagination and
  filters → API params, CSV link, "Not stated" salaries, skill toolkit explicit zeros.

### End-to-end (`frontend/e2e/dashboard.spec.ts`, Playwright)
Desktop (1440×900) and Pixel 7: KPIs equal API values, all 7 pages reachable, no horizontal
overflow, jobs search/filter/pagination, skills page (toolkit, table, trend, category filter),
salary groups match API, sources attribution, CSV export only from permitted sources, OpenAPI docs,
422 on invalid input, 405 on writes, no credentials in bundle or API responses, no console errors.

## Latest results

Recorded only from commands actually run. Dates are UTC.

| Layer | Date | Result |
|---|---|---|
| Backend unit + integration (local PostgreSQL 17) | 2026-10-29 | **160 passed** (134 unit, 26 integration); coverage 89 % of `backend/` excluding tests |
| Ruff / format / mypy | 2026-10-29 | clean; mypy: no issues in 44 files |
| `alembic check` | 2026-10-29 | "No new upgrade operations detected" |
| Frontend Vitest | 2026-10-29 | **22 passed** (2 files) |
| Frontend lint / typecheck / build | 2026-10-29 | clean; build 710 kB JS (210 kB gzip) |
| Playwright e2e against local stack (real data from a local ingestion run) | 2026-10-29 | **18 passed** (9 tests × desktop, mobile) |
| CI on GitHub (run 40830848766, commit `94b2918`) | 2026-10-29 | **success** — backend 160 passed, coverage 89 %; frontend 22 passed; lint, types, build, `alembic check` clean; gitleaks: no leaks found |
| Playwright e2e against production, run from this machine | 2026-10-29 | **18 passed** (desktop + Pixel 7) |
| Production smoke workflow on GitHub runners (run 40836104559) | 2026-10-29 | **18 passed** |
| Production privilege verification (`roles verify`) | 2026-10-29 | 16/16 PASS |
