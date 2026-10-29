# API reference

Base path: `/api/v1`. All endpoints are **GET** (other methods return 405). Interactive OpenAPI docs:
`/api/docs` (Swagger UI), `/api/redoc`, schema at `/api/openapi.json`.

Production base URL: see the README "Live deployment" section (only verified URLs are listed there).

## Conventions

- JSON responses; unknown values are `null`.
- Errors: `{"detail": ...}` — 404 not found, 405 method not allowed, 422 invalid parameters
  (field locations and messages only; submitted values are not echoed), 503 database unavailable
  (with `Retry-After`), 500 generic. Internal details are never returned.
- Caching: analytics responses send `Cache-Control: public, max-age=60, s-maxage=300`; health,
  errors and CSV are `no-store`.
- CORS: only origins in `CORS_ORIGINS`.

### Period filters (shared)

Used by `summary`, `analytics/*`, `skills`, `skills/trends`, `exports/skills.csv`, `exports/observations.csv`.

| Param | Type | Default | Notes |
|---|---|---|---|
| `start` | date | `end − 29 days` | UTC, inclusive |
| `end` | date | today (UTC) | must be ≥ `start`; range ≤ 730 days |
| `source` | `^[a-z0-9_-]{1,40}$` | — | e.g. `jobicy` |
| `role` | string ≤ 120 | — | role label; `Unclassified` for null roles |
| `country` | string ≤ 120 | — | country label; `Unspecified` for null |
| `work_mode` | `remote`/`hybrid`/`onsite` | — | |

The **population** for period metrics = distinct listings observed at least once in the window
matching the filters (see [DATA_DICTIONARY.md](DATA_DICTIONARY.md#metric-definitions)).

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | `{"status": "ok"|"degraded", "database": "ok"|"unavailable"|"not_configured", "version"}` |
| `GET /summary` | KPIs: totals by status, population size, new in period, observations, skills identified, salary disclosure, sources enabled/healthy, latest run, freshness |
| `GET /analytics/timeline` | per date: `listings_observed`, `listings_first_seen`, `reported_closed` |
| `GET /jobs` | paginated listings (see below) |
| `GET /jobs/{job_id}` | one listing + up to 120 daily observations + attribution |
| `GET /skills` | all active skills with `listings`, `share_pct`, previous-period values and change; params `category`, `q` |
| `GET /skills/trends` | `skill` (repeatable, 1–8 slugs), `grain=day|week` → per period share |
| `GET /analytics/roles` | role categories, top titles, seniority, top companies (`limit` 5–50) |
| `GET /analytics/locations` | countries, original location strings, work-mode distribution with basis |
| `GET /analytics/salaries` | disclosure, distributions per (currency, period), median by role (n ≥ 3), monthly trend (n ≥ 3) |
| `GET /analytics/lifecycle` | status counts with persistence, and source × role coverage |
| `GET /sources` | source registry, health, freshness, counts, attribution, disabled reasons |
| `GET /ingestion-runs` | run audit log (`limit` 1–100) with data-quality warn/fail counts |
| `GET /data-quality` | checks of the latest run, or `run_id` |
| `GET /meta/filters` | values + counts for filter controls; active skills |
| `GET /exports/jobs.csv` | listings from redistributable sources (≤ 5,000 rows) |
| `GET /exports/skills.csv` | skill counts/shares for the period |
| `GET /exports/observations.csv` | daily snapshots from redistributable sources (≤ 50,000 rows) |

### `GET /jobs`

| Param | Values |
|---|---|
| `q` | ≤ 100 chars; case-insensitive contains-match on title or company (`%`, `_` are literal) |
| `company` | contains-match |
| `role`, `country`, `source`, `work_mode` | as above |
| `employment_type` | `full_time`, `part_time`, `contract`, `temporary`, `internship`, `freelance` |
| `skill` | skill slug (`^[a-z0-9-]{1,60}$`) |
| `salary_disclosed` | `true` / `false` |
| `status` | `active` (default), `unconfirmed`, `expired`, `all` |
| `sort` | `first_seen_desc` (default), `last_seen_desc`, `published_desc`, `title_asc`, `company_asc`, `salary_desc` (orders within currency; never converts) |
| `page` | 1–10,000 |
| `page_size` | 1–100 (default 25) |

Response: `{"items": [...], "total", "page", "page_size", "pages"}`.

## Examples

```bash
curl "$API/api/v1/summary?start=2026-10-01&end=2026-10-31"
curl "$API/api/v1/skills?role=Data%20Analyst&category=BI%20%26%20visualization"
curl "$API/api/v1/skills/trends?skill=sql&skill=python&grain=week"
curl "$API/api/v1/jobs?skill=power-bi&salary_disclosed=true&sort=salary_desc&page_size=10"
curl -OJ "$API/api/v1/exports/jobs.csv?role=Data%20Engineer"
```

## Running locally

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
# http://localhost:8000/api/docs
```
Requires `API_DATABASE_URL` (read-only role) in the environment or `.env`.
