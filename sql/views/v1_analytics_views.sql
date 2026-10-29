-- JobMarket Pulse analytics views, version 1.
-- Applied by Alembic migration 0002. DO NOT EDIT after release: create v2_*.sql plus a new
-- migration instead, so that migration history stays reproducible.
--
-- These views are the supported interface for BI tools (Power BI / Excel / Tableau) using the
-- read-only role. They exclude transient description text and internal pipeline columns.

-- One row per job with source attribution. `allow_row_export` tells consumers whether the
-- source permits redistributing row-level listing data (see docs/SOURCE_COMPLIANCE.md).
CREATE VIEW v_jobs_public AS
SELECT
    j.id AS job_id,
    j.source_id,
    s.name AS source_name,
    j.canonical_url,
    j.title_original,
    j.title_normalized,
    COALESCE(j.role_category, 'Unclassified') AS role_category,
    j.company,
    j.location_original,
    j.city,
    j.region,
    j.country,
    j.work_mode,
    j.work_mode_basis,
    j.employment_type,
    j.seniority,
    j.salary_text,
    j.salary_min,
    j.salary_max,
    j.salary_currency,
    j.salary_period,
    j.published_at,
    j.first_seen_at,
    j.last_seen_at,
    j.last_verified_active_at,
    j.status,
    j.status_changed_at,
    j.source_reported_closed_at,
    j.skills_dictionary_version,
    s.allow_row_export,
    s.attribution
FROM jobs j
JOIN sources s ON s.id = j.source_id;

-- Skills of each job, restricted to the dictionary version of that job's latest extraction,
-- so a job is never counted under two rule sets at once.
CREATE VIEW v_job_skills_current AS
SELECT
    js.job_id,
    sk.slug AS skill_slug,
    sk.name AS skill_name,
    sk.category AS skill_category,
    js.dictionary_version,
    js.matched_in
FROM job_skills js
JOIN jobs j ON j.id = js.job_id AND js.dictionary_version = j.skills_dictionary_version
JOIN skills sk ON sk.id = js.skill_id;

-- Daily activity per source: distinct listings observed that day (feed or status check) and
-- listings first observed by this pipeline that day. "First seen" is NOT the publication date.
CREATE VIEW v_daily_listing_activity AS
SELECT
    o.observation_date,
    o.source_id,
    count(DISTINCT o.job_id) AS listings_observed,
    count(DISTINCT o.job_id) FILTER (
        WHERE (j.first_seen_at AT TIME ZONE 'UTC')::date = o.observation_date
    ) AS listings_first_seen
FROM job_observations o
JOIN jobs j ON j.id = o.job_id
GROUP BY o.observation_date, o.source_id;

-- Skill share among CURRENTLY ACTIVE listings.
-- share_pct = distinct active listings mentioning the skill / distinct active listings * 100.
CREATE VIEW v_skill_share_active AS
WITH eligible AS (
    SELECT id FROM jobs WHERE status = 'active'
), total AS (
    SELECT count(*) AS n FROM eligible
)
SELECT
    sk.slug AS skill_slug,
    sk.name AS skill_name,
    sk.category AS skill_category,
    count(DISTINCT v.job_id) AS listings,
    t.n AS eligible_listings,
    round(100.0 * count(DISTINCT v.job_id) / NULLIF(t.n, 0), 2) AS share_pct
FROM skills sk
CROSS JOIN total t
LEFT JOIN v_job_skills_current v
    ON v.skill_slug = sk.slug AND v.job_id IN (SELECT id FROM eligible)
WHERE sk.active
GROUP BY sk.slug, sk.name, sk.category, t.n;

-- Salary disclosure per source and role among active listings. "comparable" = numeric range
-- with a known currency AND pay period (usable in currency/period-specific statistics).
CREATE VIEW v_salary_disclosure AS
SELECT
    j.source_id,
    COALESCE(j.role_category, 'Unclassified') AS role_category,
    count(*) AS listings,
    count(*) FILTER (WHERE j.salary_text IS NOT NULL OR j.salary_min IS NOT NULL
                       OR j.salary_max IS NOT NULL) AS with_salary_info,
    count(*) FILTER (WHERE (j.salary_min IS NOT NULL OR j.salary_max IS NOT NULL)
                       AND j.salary_currency IS NOT NULL AND j.salary_period IS NOT NULL)
        AS with_comparable_salary
FROM jobs j
WHERE j.status = 'active'
GROUP BY j.source_id, COALESCE(j.role_category, 'Unclassified');

-- Source health and freshness.
CREATE VIEW v_source_health AS
SELECT
    s.id AS source_id,
    s.name,
    s.enabled,
    s.access_method,
    s.homepage_url,
    s.attribution,
    s.allow_row_export,
    s.disabled_reason,
    s.last_attempt_at,
    s.last_success_at,
    s.last_fetch_complete,
    s.last_record_count,
    s.last_error_at,
    s.last_error_summary,
    (SELECT count(*) FROM jobs j WHERE j.source_id = s.id) AS jobs_total,
    (SELECT count(*) FROM jobs j WHERE j.source_id = s.id AND j.status = 'active') AS jobs_active
FROM sources s;
