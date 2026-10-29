# Data dictionary

Field-level definitions for the API, CSV exports and BI views. Unknown values are always `null`
(blank in CSV) — never `0`, never a guess.

## Timestamps — what each one means

| Field | Meaning | Is NOT |
|---|---|---|
| `published_at` | Publication time supplied by the source. | Verified by us; may be null. |
| `first_seen_at` | When this pipeline first observed the listing. | The posting date. A listing published before the project started shows the project start. |
| `last_seen_at` | Most recent run in which the listing appeared in the source **feed**. | Proof it is still open. |
| `last_verified_active_at` | Most recent time the source's status API said "active" (Jobicy). | — |
| `source_reported_closed_at` | When we received an explicit "closed" from the source. | The exact closing time. |
| `status_changed_at` | When the pipeline last changed `status`. | — |
| `observation_date` | UTC date of a snapshot row. | — |

All timestamps are stored as `timestamptz`; API responses are ISO 8601; dashboard dates are UTC.

## Listing status

| Status | Rule | Evidence |
|---|---|---|
| `active` | Seen in the latest complete feed, or confirmed active by the source's status API. | Direct |
| `unconfirmed` (UI: "Not seen recently") | Absent from **2 consecutive complete, non-anomalous, non-empty** feeds of its source and not confirmed active by a status API. | Indirect — feeds are rolling windows, so this is a *possible* disappearance |
| `expired` (UI: "Reported closed") | The source's status API returned `closed`. | Direct |

A failed, partial, empty or anomalously small fetch never changes any status. Re-appearing
listings return to `active`. Observations are never deleted.

## Job fields

| Field | Type | Description |
|---|---|---|
| `id` | integer | Internal id |
| `source_id` / `source_name` | text | `jobicy`, `remoteok` |
| `url` (`canonical_url`) | text | Link to the original listing (tracking parameters removed) |
| `title` (`title_original`) | text | As published (HTML entities decoded) |
| `title_normalized` | text | Whitespace collapsed; `Sr.`→Senior, `Jr.`→Junior; `| Country | Remote` and `(Remote)` suffixes removed. Meaningful qualifiers kept. |
| `role_category` | text/null | First matching rule in `config/roles.toml` (Analytics Engineer, Machine Learning Engineer, Data Engineer, Data Scientist, Business Intelligence Analyst, Data Analyst, Business Analyst, DevOps / Cloud Engineer, Software Engineer). Null = "Unclassified". |
| `company` | text/null | As published |
| `location` (`location_original`) | text/null | As published |
| `city`, `region`, `country` | text/null | Filled only for a single known country, "City, US-state", "City, Indian-state", or "City, Country". Region words (Europe, EMEA, APAC…) and lists stay unstructured. API/BI label for null country: `Unspecified`. |
| `work_mode` | `remote`/`hybrid`/`onsite`/null | Hybrid/on-site only from explicit title/location wording; otherwise the board default (`remote`). |
| `work_mode_basis` | `text`/`source_default` | How `work_mode` was decided |
| `employment_type` | `full_time`, `part_time`, `contract`, `temporary`, `internship`, `freelance`, null | From source field (Jobicy `jobType`) |
| `seniority` | `intern`, `junior`, `mid`, `senior`, `lead`, `staff`, `principal`, `manager`, `director`, `executive`, null | Source level if recognised, else title keywords |
| `salary_text` | text/null | Original salary representation (for structured sources, rebuilt from the source fields, e.g. `82,988–99,586 EUR yearly`) |
| `salary_min`, `salary_max` | number/null | Only when unambiguous and consistent |
| `salary_currency` | ISO 4217 code/null | Never converted |
| `salary_period` | `hour`/`day`/`week`/`month`/`year`/null | Never annualised |
| `skills` | list | Skills detected with the job's current dictionary version |
| `status` | see above | |

## Salary rules

1. Missing salary → all salary fields null (Remote OK `0` means "not provided" → null).
2. Structured source fields are used when present; free text is parsed only when currency **and**
   period can be determined (`$100k - $140k per year`, `€50,000–60,000 annually`, `12-18 LPA`,
   `₹8,00,000 - ₹12,00,000 per annum`, `USD 40/hour`).
3. Rejected (numbers dropped, text kept, counted in the `salary_consistency` check):
   `min > max`, `max > 10 × min`, values outside generous per-period bounds (e.g. a yearly salary
   below 1,000 or an hourly rate above 20,000), unknown currency codes.
4. Remote OK amounts have no stated currency/period → kept as amounts with
   `salary_currency = null`, `salary_period = null`, and excluded from salary statistics
   (reported as "amount without unit").
5. Statistics are computed per `(currency, period)` on the range **midpoint**
   (`(min + max) / 2`, or the single value).

## Skill extraction

- Dictionary: [`config/skills.toml`](../config/skills.toml), version `2026.10.1`, 50 skills in 8
  categories (programming languages; data analysis; databases & SQL; BI & visualization; machine
  learning; data engineering; cloud & DevOps; spreadsheets & office).
- Fields scanned: original title, source tags, description text (description is not stored for
  Remote OK and is purged after 30 days for Jobicy).
- Matching: each alias is bounded — not preceded or followed by a letter, digit, `_`, `+`, `#`, and
  not followed by `.<alnum>`. Some aliases are case-sensitive (`R`, `Excel`, `Spark`, `NLP`, `LLM`,
  `Snowflake`); `not_followed_by` vetoes verb uses (e.g. "Excel at", "excel in").
- Known limitations: the standalone capital letter "R" can still match in rare non-language
  contexts; skills mentioned only in links/images are missed; synonyms not in the dictionary are missed.
- Versioning: links are stored per `dictionary_version`; statistics use each job's current version.
  After changing the dictionary, bump `version` and run
  `python -m backend.ingestion.cli reprocess-skills` (re-extracts jobs whose text is still retained;
  others are re-extracted when next seen in a feed).

## Metric definitions

| Metric | Definition | Denominator |
|---|---|---|
| **Population (period)** | Distinct listings with ≥ 1 observation between `start` and `end` (UTC) matching the filters | — |
| Active listings | `status = 'active'` (not period-filtered) | — |
| New in period | Listings in the population whose `first_seen_at` date is in the period | — |
| Skill share | Distinct listings in the population mentioning the skill × 100 | Distinct listings in the population |
| Previous-period share | Same, for the immediately preceding window of equal length | Its own population |
| Change | `share − previous share`, in percentage points | — |
| Skill trend point | Distinct listings observed in that day/week mentioning the skill × 100 | Distinct listings observed in that day/week |
| Salary disclosure rate | Listings with any salary text or amount × 100 | Population |
| Comparable salary rate | Listings with amount + currency + period × 100 | Population |
| Salary distribution | min, 25th, median, 75th percentile, max of midpoints per (currency, period) | Listings in that group |
| Median salary by role | Median midpoint per (role, currency, period); groups with < 3 listings hidden | — |
| Listings observed (timeline) | Distinct listings with an observation on that date | — |
| Data freshness | Hours since the latest `succeeded`/`partial` run finished: fresh ≤ 30 h, delayed ≤ 54 h, else stale | — |
| Source health | `healthy` (complete success within 36 h), `degraded`, `failing`, `never_run`, `disabled` | — |

Skill shares are never divided by observation rows: a listing seen on 10 days counts once.

## Data-quality checks

Recorded per source per run in `data_quality_results`:

| Check | Fail/warn condition |
|---|---|
| `fetch_completeness` | warn if any page failed or the page cap was hit; fail if nothing could be fetched |
| `required_fields_and_formats` | invalid records (missing id/title/URL, URL host not the source's, future or pre-2000 publication date, bad enum, inconsistent salary fields). Reasons stored without values. Fail if > 10 % of in-scope records are invalid (the run becomes `partial`). |
| `duplicate_listings` | warn when the same `dedup_key` appears twice in a fetch (first occurrence kept) |
| `salary_consistency` | warn when salary numbers were rejected |
| `record_count_anomaly` | warn when fetched < 50 % of the median of the last ≥ 3 complete fetches (baseline ≥ 20); blocks absence inference |
| `batch_schema` | Pandera checks on the batch (unique keys, https URLs, enums, currency format, min ≤ max); fail blocks the write for that source |
| `post_write_integrity` (all sources) | duplicate snapshots, jobs seen today without an observation, `first_seen > last_seen`, `min > max` — all must be 0 |

## CSV exports

| Endpoint | Rows | Sources |
|---|---|---|
| `/api/v1/exports/jobs.csv` | ≤ 5,000 listings (fields in the table above + `attribution`) | only `allow_row_export = true` (Jobicy) |
| `/api/v1/exports/skills.csv` | one row per skill with counts and shares for the period | all (aggregate) |
| `/api/v1/exports/observations.csv` | ≤ 50,000 daily snapshot rows in the period | only `allow_row_export = true` |

Cells beginning with `= + - @` are prefixed with `'` to prevent spreadsheet formula injection.
Descriptions are never exported.
