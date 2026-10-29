# Power BI, Excel and Tableau guide

Three ways to analyse JobMarket Pulse data outside the dashboard, from simplest to most flexible.
None of them requires the ingestion or migration credentials — **never give those to a BI tool.**

## Option 1 — CSV exports (no credentials)

| File | URL (replace `$API` with the API base URL from the README) |
|---|---|
| Listings (redistributable sources only) | `$API/api/v1/exports/jobs.csv?status=all` |
| Skill shares for a period | `$API/api/v1/exports/skills.csv?start=2026-10-01&end=2026-10-31` |
| Daily observations (history) | `$API/api/v1/exports/observations.csv?start=2026-10-01&end=2026-10-31` |

The same filter parameters as the API apply (`role`, `country`, `source`, …). Row caps: 5,000 jobs,
50,000 observations. Remote OK rows are excluded from row-level exports by design (see
[SOURCE_COMPLIANCE.md](SOURCE_COMPLIANCE.md)).

### Excel
1. *Data → Get Data → From Web*, paste the CSV URL, *Load* (Excel uses Power Query).
2. Set column types: dates/timestamps → Date/Time (values are UTC ISO-8601), `salary_min/max` →
   Decimal. Blank salary cells mean **unknown** — do not replace them with 0.
3. *Refresh All* re-downloads the latest data.

### Power BI Desktop (web source)
1. *Get data → Web*, paste the CSV URL (Basic, anonymous).
2. In Power Query, check types as above and keep `salary_currency` and `salary_period` as text.
3. Publish; in the Power BI service, set scheduled refresh for the web source (anonymous access
   is supported for public URLs). Refresh after 05:00 UTC to pick up the daily run.

## Option 2 — JSON API (Power Query)

```powerquery
let
    Source = Json.Document(Web.Contents("https://<api-host>", [RelativePath = "api/v1/skills",
        Query = [start = "2026-10-01", end = "2026-10-31"]])),
    Items = Table.FromRecords(Source[items])
in
    Items
```
Use `RelativePath` + `Query` so the Power BI service can refresh the dataset.

## Option 3 — direct PostgreSQL (read-only role)

Only for people you trust with a database login. Use the **read-only** role (`jmp_api_ro`) or,
better, a dedicated read-only role created the same way (`backend/ops/roles.py` shows the grants).

- Host: the Neon **pooled** host for the project; port 5432; database `neondb` (this deployment); SSL
  required (`sslmode=require`).
- Power BI: *Get data → PostgreSQL database*; Import mode recommended (Neon Free computes suspend
  after 5 minutes of inactivity; DirectQuery would keep waking it and consume compute hours).
- Connect only to the **views**, which are the supported BI interface:

| View | Use |
|---|---|
| `v_jobs_public` | fact table of listings (filter `allow_row_export = true` if you redistribute results) |
| `v_job_skills_current` | job ↔ skill bridge (current dictionary version) |
| `v_daily_listing_activity` | daily counts per source |
| `v_skill_share_active` | ready-made skill share among active listings |
| `v_salary_disclosure` | disclosure counts per source and role |
| `v_source_health` | freshness and health |

Suggested model: `v_jobs_public[job_id]` 1—* `v_job_skills_current[job_id]`; build a Date table and
relate it to `first_seen_at` (date part).

Example DAX measures (respecting the project's denominators):

```dax
Listings = DISTINCTCOUNT ( v_jobs_public[job_id] )
Listings with skill = CALCULATE ( [Listings], v_job_skills_current )
Skill share % = DIVIDE ( [Listings with skill], [Listings] ) * 100
Salary disclosed % =
    DIVIDE ( CALCULATE ( [Listings], NOT ISBLANK ( v_jobs_public[salary_text] ) ), [Listings] ) * 100
```

Never average `salary_min/max` across different `salary_currency` or `salary_period` values; put
both columns on the visual or filter to one combination.

SQL examples ready to paste into a PostgreSQL client are in [`sql/examples/`](../sql/examples).

## Tableau
*Connect → PostgreSQL* with the read-only credentials, or *Text file* for downloaded CSVs. Use the
same views and the same rules for salaries and denominators.

## Network and credential notes
- Neon accepts connections from any IP unless an IP allow-list is configured; check Neon's current
  plan documentation before relying on one. Protect credentials and rotate them if shared (see the
  runbook).
- Read-only connections cannot change data: the role has SELECT-only grants and read-only
  transactions by default.
