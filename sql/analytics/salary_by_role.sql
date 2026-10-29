-- Median salary midpoint per role inside one (currency, period) group; groups with fewer
-- than :min_n listings are omitted to avoid over-reading tiny samples.
WITH population AS ({{population(start, end)}})
SELECT j.salary_currency AS currency, j.salary_period AS period,
       COALESCE(j.role_category, 'Unclassified') AS role, count(*) AS listings,
       percentile_cont(0.5) WITHIN GROUP (
           ORDER BY (COALESCE(j.salary_min, j.salary_max)
                     + COALESCE(j.salary_max, j.salary_min)) / 2.0
       ) AS median
FROM population p JOIN jobs j ON j.id = p.id
WHERE j.salary_currency IS NOT NULL AND j.salary_period IS NOT NULL
  AND (j.salary_min IS NOT NULL OR j.salary_max IS NOT NULL)
GROUP BY 1, 2, 3
HAVING count(*) >= :min_n
ORDER BY currency, period, median DESC
