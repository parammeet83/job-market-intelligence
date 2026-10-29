-- Values offered in dashboard filter controls, with counts over all stored listings.
SELECT 'role' AS kind, COALESCE(role_category, 'Unclassified') AS value, count(*) AS n
FROM jobs GROUP BY 2
UNION ALL
SELECT 'country', COALESCE(country, 'Unspecified'), count(*) FROM jobs GROUP BY 2
UNION ALL
SELECT 'source', source_id, count(*) FROM jobs GROUP BY 2
UNION ALL
SELECT 'work_mode', work_mode, count(*) FROM jobs WHERE work_mode IS NOT NULL GROUP BY 2
UNION ALL
SELECT 'employment_type', employment_type, count(*) FROM jobs
WHERE employment_type IS NOT NULL GROUP BY 2
UNION ALL
SELECT 'skill_category', category, count(*) FROM skills WHERE active GROUP BY 2
ORDER BY 1, 3 DESC, 2
