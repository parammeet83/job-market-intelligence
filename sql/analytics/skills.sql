-- Skill ranking with period-over-period comparison.
-- share_pct = distinct listings in POPULATION(:start, :end) mentioning the skill
--             / distinct listings in that population * 100.
-- prev_* uses the immediately preceding window of equal length (:prev_start, :prev_end).
-- Skills come from each job's latest extraction (job_skills.dictionary_version =
-- jobs.skills_dictionary_version), so no job is counted under two dictionary versions.
WITH population AS ({{population(start, end)}}),
prev_population AS ({{population(prev_start, prev_end)}}),
cur AS (
    SELECT js.skill_id, count(DISTINCT p.id) AS listings
    FROM population p
    JOIN jobs j ON j.id = p.id
    JOIN job_skills js ON js.job_id = j.id AND js.dictionary_version = j.skills_dictionary_version
    GROUP BY js.skill_id
),
prev AS (
    SELECT js.skill_id, count(DISTINCT p.id) AS listings
    FROM prev_population p
    JOIN jobs j ON j.id = p.id
    JOIN job_skills js ON js.job_id = j.id AND js.dictionary_version = j.skills_dictionary_version
    GROUP BY js.skill_id
),
totals AS (
    SELECT (SELECT count(*) FROM population) AS n, (SELECT count(*) FROM prev_population) AS prev_n
)
SELECT
    sk.slug,
    sk.name,
    sk.category,
    COALESCE(cur.listings, 0) AS listings,
    t.n AS eligible_listings,
    round(100.0 * COALESCE(cur.listings, 0) / NULLIF(t.n, 0), 2) AS share_pct,
    COALESCE(prev.listings, 0) AS prev_listings,
    t.prev_n AS prev_eligible_listings,
    round(100.0 * COALESCE(prev.listings, 0) / NULLIF(t.prev_n, 0), 2) AS prev_share_pct
FROM skills sk
CROSS JOIN totals t
LEFT JOIN cur ON cur.skill_id = sk.id
LEFT JOIN prev ON prev.skill_id = sk.id
WHERE sk.active
  AND (CAST(:category AS text) IS NULL OR sk.category = :category)
  AND (CAST(:q AS text) IS NULL OR sk.name ILIKE :q ESCAPE '\')
ORDER BY listings DESC, sk.name
