-- Salary distribution per (currency, pay period). Currencies are never converted and
-- periods are never mixed. Statistic = midpoint of each listing's range
-- ((min + max) / 2, or the single published value).
WITH population AS ({{population(start, end)}}),
salaries AS (
    SELECT j.salary_currency AS currency, j.salary_period AS period,
           j.salary_min, j.salary_max,
           (COALESCE(j.salary_min, j.salary_max) + COALESCE(j.salary_max, j.salary_min)) / 2.0
               AS midpoint
    FROM population p JOIN jobs j ON j.id = p.id
    WHERE j.salary_currency IS NOT NULL AND j.salary_period IS NOT NULL
      AND (j.salary_min IS NOT NULL OR j.salary_max IS NOT NULL)
)
SELECT currency, period, count(*) AS listings,
       min(COALESCE(salary_min, salary_max)) AS min_value,
       percentile_cont(0.25) WITHIN GROUP (ORDER BY midpoint) AS p25,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY midpoint) AS median,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY midpoint) AS p75,
       max(COALESCE(salary_max, salary_min)) AS max_value
FROM salaries
GROUP BY currency, period
ORDER BY listings DESC, currency, period
