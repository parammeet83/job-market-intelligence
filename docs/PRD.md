# Product requirements — JobMarket Pulse

## Problem
People choosing what to learn for data and software roles rely on anecdotes or one-off snapshots.
Public job boards show current postings but not history, and they rarely quantify which skills
are asked for, how often salaries are published, or how the mix changes over time.

## Goal
An open, reproducible, automatically refreshed **historical dataset** of public tech/data job
listings, with transparent analytics on skills, roles, locations, salaries and listing lifecycle.

## Users
| User | Need |
|---|---|
| Job seeker / student (e.g. aspiring data analyst) | Which skills (SQL, Python, Excel, Power BI, Tableau…) appear most in relevant listings; salary transparency |
| Recruiter / hiring manager reviewing this portfolio | Evidence of end-to-end data engineering: ingestion, modelling, quality, analytics, deployment |
| Analyst | Clean CSVs/BI views with clear definitions and denominators |

## Scope (v1)
In scope:
- Daily collection from sources whose terms permit it (Jobicy, Remote OK).
- Role categories: Data Analyst, Data Engineer, Business Analyst, BI Analyst, Data Scientist,
  ML Engineer, Analytics Engineer, Software Engineer (+ DevOps/Cloud). Configurable.
- Skill dictionary of 50 skills in 8 categories, versioned.
- Historical daily observations; lifecycle statuses with evidence levels.
- Dashboard pages: Overview, Job Listings, Skill Intelligence, Salary Insights, Locations & Roles,
  Data Sources, Methodology.
- Read-only public API with OpenAPI docs; CSV exports respecting source terms; BI guide.
- Free-tier hosting only.

Out of scope (v1): user accounts, alerts, write APIs, scraping restricted boards (LinkedIn,
Indeed, Glassdoor, Naukri), currency conversion, LLM-based extraction, full-text descriptions.

## Functional requirements
1. Ingestion runs daily and on demand; one failing source does not block others.
2. Re-running the same data creates no duplicate listings, observations or skill links.
3. Every listing links to its original source; attribution is visible.
4. Skill share uses distinct listings as numerator and denominator within the selected population.
5. Salaries are shown per currency and pay period; missing salary is never shown as zero.
6. Every chart has loading, empty, error/retry states and a table view; no fabricated numbers.
7. Filters (period, role, country, source, work mode; plus job-specific filters) work everywhere they are shown and are shareable via the URL.
8. Small samples are flagged.

## Non-functional requirements
- Public API is read-only at the HTTP, transaction and database-role levels.
- No secrets in the repo, browser bundle, logs or API responses.
- Usable on a 390 px-wide phone without horizontal scrolling; keyboard accessible.
- Zero cost: no billing, no paid trials, no paid fallbacks.

## Success criteria
- Daily scheduled run succeeds and the dashboard freshness is "Fresh" most days.
- Numbers on the dashboard match direct SQL against the database (automated tests).
- Documentation lets a new contributor run the pipeline locally in under 15 minutes.

## Known limitations (accepted for v1)
- Coverage is limited to two remote-focused boards; India coverage is incidental.
- Trend views need weeks of history to be meaningful.
- "Not seen recently" is an inference, not a verified closure.
