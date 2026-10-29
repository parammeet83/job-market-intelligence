-- Monthly median salary midpoint per (currency, period) using observation months.
-- Months with fewer than :min_n listings are omitted.
SELECT CAST(date_trunc('month', CAST(o.observation_date AS timestamp)) AS date) AS month,
       j.salary_currency AS currency, j.salary_period AS period,
       count(DISTINCT j.id) AS listings,
       percentile_cont(0.5) WITHIN GROUP (
           ORDER BY (COALESCE(j.salary_min, j.salary_max)
                     + COALESCE(j.salary_max, j.salary_min)) / 2.0
       ) AS median
FROM job_observations o
JOIN jobs j ON j.id = o.job_id
WHERE o.observation_date BETWEEN :start AND :end
  AND {{job_filters}}
  AND j.salary_currency IS NOT NULL AND j.salary_period IS NOT NULL
  AND (j.salary_min IS NOT NULL OR j.salary_max IS NOT NULL)
GROUP BY 1, 2, 3
HAVING count(DISTINCT j.id) >= :min_n
ORDER BY 1, 2, 3
