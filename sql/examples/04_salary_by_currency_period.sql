-- Salary midpoint distribution, never mixing currencies or pay periods.
SELECT salary_currency, salary_period, count(*) AS listings,
       percentile_cont(0.5) WITHIN GROUP (
           ORDER BY (COALESCE(salary_min, salary_max) + COALESCE(salary_max, salary_min)) / 2.0
       ) AS median_midpoint
FROM v_jobs_public
WHERE status = 'active' AND salary_currency IS NOT NULL AND salary_period IS NOT NULL
  AND (salary_min IS NOT NULL OR salary_max IS NOT NULL)
GROUP BY salary_currency, salary_period
ORDER BY listings DESC;
