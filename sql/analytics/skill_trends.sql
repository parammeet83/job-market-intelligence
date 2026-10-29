-- Skill share per period (day or week) for selected skills.
-- For each period: eligible = distinct filtered listings observed in that period;
-- share_pct = listings mentioning the skill / eligible * 100.
WITH obs AS (
    SELECT DISTINCT
        CAST(date_trunc(CAST(:grain AS text), CAST(o.observation_date AS timestamp)) AS date)
            AS period,
        o.job_id
    FROM job_observations o
    JOIN jobs j ON j.id = o.job_id
    WHERE o.observation_date BETWEEN :start AND :end
      AND {{job_filters}}
),
totals AS (
    SELECT period, count(*) AS n FROM obs GROUP BY period
),
hits AS (
    SELECT obs.period, sk.slug, count(DISTINCT obs.job_id) AS listings
    FROM obs
    JOIN jobs j ON j.id = obs.job_id
    JOIN job_skills js ON js.job_id = j.id AND js.dictionary_version = j.skills_dictionary_version
    JOIN skills sk ON sk.id = js.skill_id
    WHERE sk.slug = ANY(CAST(:skills AS text[]))
    GROUP BY obs.period, sk.slug
)
SELECT
    t.period,
    s.slug,
    COALESCE(h.listings, 0) AS listings,
    t.n AS eligible_listings,
    round(100.0 * COALESCE(h.listings, 0) / NULLIF(t.n, 0), 2) AS share_pct
FROM totals t
CROSS JOIN unnest(CAST(:skills AS text[])) AS s(slug)
LEFT JOIN hits h ON h.period = t.period AND h.slug = s.slug
ORDER BY t.period, s.slug
