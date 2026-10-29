# Data sources

Configuration lives in [`config/sources.toml`](../config/sources.toml); adapters live in
[`backend/ingestion/sources/`](../backend/ingestion/sources). Permissions are documented in
[SOURCE_COMPLIANCE.md](SOURCE_COMPLIANCE.md).

## Enabled sources

### Jobicy (`jobicy`)

| Item | Value |
|---|---|
| Endpoint | `GET https://jobicy.com/api/jobs` |
| Passes | one per configured industry: `data-science`, `engineering`, `admin` (DevOps & Infrastructure) |
| Paging | `count=200`, opaque `cursor` (`nextCursor` / `hasMore`), max 10 pages per industry |
| Window | jobs published in the last 7 days |
| Closure evidence | `GET /api/jobs/status?ids=…` → `active` / `closed` / `unknown` (up to 1,000 ids per run, least-recently verified first) |
| Native id | `id` (integer) → `source_job_id` |
| Fields used | `id, url, jobTitle, companyName, jobIndustry, jobType, jobGeo, jobLevel, jobDescription (transient), pubDate, salaryMin/Max/Currency/Period` |
| Scope | every job from the configured industries (role category may be "Unclassified") |
| Work mode | board lists remote jobs → `remote` with basis `source_default`, unless the title/location says hybrid or on-site |
| Export | row-level CSV permitted |

Observed in development (2026-10-29): 3 industry passes returned 343 jobs in 4 requests.

### Remote OK (`remoteok`)

| Item | Value |
|---|---|
| Endpoint | `GET https://remoteok.com/api` |
| Paging | none — one request returns the latest ~100 listings (element 0 is a legal notice) |
| Native id | `id` (string) |
| Fields used | `id, url, position, company, location, tags, description (transient), date/epoch, salary_min/max` |
| Scope | only titles matching a configured tech/data role (`require_role_match = true`); others are counted as *out of scope* |
| Salary | amounts only — currency and pay period are **not stated**, so they are stored as unknown |
| Export | aggregates only (row-level CSV disabled) |

Observed in development (2026-10-29): 99 listings, 21 in scope.

## Disabled sources

`arbeitnow` and `remotive` are listed in the configuration with `enabled = false` and a
`disabled_reason`, so the dashboard can show why. No adapter is implemented for them.

## Coverage — what this dataset is and is not

- Both enabled sources are **remote-job boards** with an international audience and a strong
  US/Europe/UK skew. The location field is often a region ("Europe", "EMEA") or a list of countries.
- **India:** neither source offers India-specific coverage. Indian listings appear only when a
  remote board happens to carry one. The dashboard must not be read as a picture of the Indian market.
- Jobicy covers a rolling 7-day publication window; Remote OK the latest ~100 listings. Daily runs
  build history over time; the first days of history are thin.
- The dataset is a sample of public postings on two boards, not a census of jobs.

## Adding a source

1. Complete the review checklist in [SOURCE_COMPLIANCE.md](SOURCE_COMPLIANCE.md).
2. Add a `[sources.<id>]` block to `config/sources.toml` (start with `enabled = false`).
3. Implement `SourceAdapter` (`fetch`, `parse`, `health_check`, optional `check_status`) in
   `backend/ingestion/sources/<id>.py` and register it in `sources/__init__.py`.
4. Add fixture-based parser tests (`backend/tests/unit`) — synthetic records only.
5. `uv run python -m backend.ingestion.cli check-sources` and `run --dry-run --source <id>`.
6. Enable, then watch the first scheduled runs on the Data Sources page.
