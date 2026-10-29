-- Skill share per role category among active listings.
WITH active AS (
    SELECT job_id, role_category FROM v_jobs_public WHERE status = 'active'
), totals AS (
    SELECT role_category, count(*) AS n FROM active GROUP BY role_category
)
SELECT a.role_category, s.skill_name,
       count(DISTINCT a.job_id) AS listings,
       t.n AS role_listings,
       round(100.0 * count(DISTINCT a.job_id) / t.n, 1) AS share_pct
FROM active a
JOIN v_job_skills_current s ON s.job_id = a.job_id
JOIN totals t ON t.role_category = a.role_category
GROUP BY a.role_category, s.skill_name, t.n
HAVING t.n >= 10
ORDER BY a.role_category, share_pct DESC;
