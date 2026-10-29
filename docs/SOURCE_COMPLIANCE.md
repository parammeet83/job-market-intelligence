# Source compliance

This document records **why** each job-data source is enabled or disabled. It reflects the
terms and documentation reviewed on **2026-10-29**. Terms can change; re-check them before
enabling a new source or changing how data is used (see the review checklist at the end).

Principles applied:

- Only documented APIs/feeds are used. No HTML scraping, no logins, no CAPTCHA or bot-protection
  bypass, no IP rotation, no paid scraping services.
- A public URL is not treated as permission. When a source's terms are unclear, it stays
  **disabled** (`enabled = false` in `config/sources.toml`).
- `robots.txt` was checked as one input, not as a substitute for the terms.
- Requests identify the project in the `User-Agent`, are at least 2 seconds apart, use bounded
  retries, and honour HTTP 429 / `Retry-After`.
- Each source is only queried at hosts on its allow-list (SSRF protection, see `backend/ingestion/http.py`).

## Decision summary

| Source | Status | Collection | Storage of history | Aggregates | Row-level CSV export | Attribution |
|---|---|---|---|---|---|---|
| Jobicy | **Enabled** | Permitted (public API, no key) | Permitted ("store, cache, process") | Permitted | **Permitted** ("redistribute job data as needed") | Credit Jobicy with a link; apply links must go to the Jobicy listing |
| Remote OK | **Enabled** | Permitted (public API with ToS notice) | Not addressed by the terms | Used | **Disabled** (aggregates only) | Followed link to the Remote OK listing + name "Remote OK"; no logo |
| Arbeitnow | Disabled | Public API exists | Unclear | — | — | Link back |
| Remotive | Disabled | Public API exists | — | — | — | Link back + name |

## Jobicy — enabled

- **Endpoint:** `GET https://jobicy.com/api/jobs` (params `count` ≤ 200, `cursor`, `industry`, `geo`, `tag`),
  plus `GET https://jobicy.com/api/jobs/status?ids=…` (≤ 100 ids) for explicit active/closed/unknown status.
- **Documentation reviewed:** https://jobicy.com/jobs-rss-feed (redirect target of `https://jobi.cy/apidocs`).
- **Automated collection:** permitted; no key required. Guidance: "Start a new automated pass no more
  than once per hour"; "Avoid excessive API requests and cache responses where appropriate";
  status checks "hourly or less often". We run **once per day** (~4 feed requests + ≤ 10 status requests).
- **Storage / analytics / redistribution:** FAQ: "You can store, cache, process, and redistribute job
  data as needed" and "make sure your listings are regularly synchronized".
- **Restrictions:** "Do not present Jobicy listings as your own original job postings or remove source
  attribution"; no spam networks or misleading job databases; apply links must point to the original
  Jobicy job page.
- **How we comply:** every listing links to its Jobicy URL (we never rewrite apply links), the
  attribution text is shown on the Data Sources page and in the API (`/api/v1/sources`, job detail
  `attribution`), and listings are re-synchronised daily with closures taken from the status API.
- **Coverage note:** the feed only contains jobs published in the last 7 days. There is no India
  geography slug (`?get=locations` lists none).
- **robots.txt:** API paths are not disallowed.

## Remote OK — enabled with restrictions

- **Endpoint:** `GET https://remoteok.com/api` (single JSON array; element 0 is a legal notice).
- **Terms reviewed:** the API's own `legal` field — "Please link back (with follow, and without
  nofollow!) to the URL on Remote OK and mention Remote OK as a source … Please don't use the Remote OK
  logo without written permission" — and https://remoteok.com/legal, which asks users of its APIs to
  "link back with a web hyperlink or in-app hyperlink to our site".
- **Storage / redistribution:** the terms do not address storing or redistributing listing data.
  We therefore:
  - store only normalized fields needed for analytics plus the listing URL;
  - **do not retain description text** (`retain_description_days = 0`);
  - **exclude Remote OK rows from row-level CSV exports** (`allow_row_export = false`); Remote OK
    contributes only to aggregate statistics and to on-site listing cards that link back.
- **Rate:** `robots.txt` sets `Crawl-delay: 1` and allows `/api`; we make one request per day.
- **Links:** listing links are plain `<a href>` with `rel="noopener noreferrer"` (no `nofollow`).
- **Salary fields:** amounts are given without currency or pay period; we keep the amounts but leave
  currency/period unknown and exclude them from salary statistics.

## Arbeitnow — disabled

- API: `https://www.arbeitnow.com/api/job-board-api` (free, no key; the API meta says "By using the
  API, you agree to the terms of service present on Arbeitnow.com" and asks for a link back).
- The site terms grant a licence "for personal, non-commercial transitory viewing only" and prohibit
  copying materials or mirroring them "on any other server"; they also say "We may revoke the
  permission to use API at any time".
- Building a stored historical dataset is not clearly permitted → **disabled** until clarified with
  the operator. (Coverage is also mostly Germany.)

## Remotive — disabled

- API: `https://remotive.com/api/remote-jobs`.
- Terms: "Please do not submit Remotive jobs to third Party websites" (examples include job
  aggregators), access can be terminated; jobs are delayed by 24 hours; "max. 4 times a day".
- A public dashboard listing Remotive jobs could be read as a third-party site → **disabled**.

## Not used

LinkedIn, Indeed, Glassdoor, Naukri and similar boards are **not** collected: their terms restrict
automated access and no official API grants the intended use.

## Retention

| Data | Retention |
|---|---|
| Normalized job fields, URLs, observations, skill links | Kept for historical analysis (facts and derived data, not copies of descriptions). |
| Description text (Jobicy only) | `job_descriptions`, purged after 30 days; used only to re-run skill extraction; never served by the API or exported. |
| Description text (Remote OK) | Not stored. |

## Review checklist (before enabling or changing a source)

1. Read the current API documentation, terms of service and `robots.txt`.
2. Record: collection allowed? storage? aggregates? redistribution/export? attribution? rate limits?
   geographic or field restrictions?
3. Update this file and `docs/DATA_SOURCES.md` with quotes and the review date.
4. Set `enabled`, `allow_row_export`, `retain_description_days`, `allowed_hosts` in `config/sources.toml`.
5. Implement and test an adapter with fixtures; run a `--dry-run` before the first real run.
