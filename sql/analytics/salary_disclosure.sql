-- Salary disclosure within POPULATION(:start, :end).
-- with_salary_info: any salary text or amount published.
-- with_comparable_salary: numeric amount AND known currency AND known pay period.
-- with_unit_unknown: amount published but currency or period not stated by the source.
-- Missing salary is unknown, never zero.
WITH population AS ({{population(start, end)}})
SELECT
    count(*) AS listings,
    count(*) FILTER (WHERE j.salary_text IS NOT NULL OR j.salary_min IS NOT NULL
                       OR j.salary_max IS NOT NULL) AS with_salary_info,
    count(*) FILTER (WHERE (j.salary_min IS NOT NULL OR j.salary_max IS NOT NULL)
                       AND j.salary_currency IS NOT NULL AND j.salary_period IS NOT NULL)
        AS with_comparable_salary,
    count(*) FILTER (WHERE (j.salary_min IS NOT NULL OR j.salary_max IS NOT NULL)
                       AND (j.salary_currency IS NULL OR j.salary_period IS NULL))
        AS with_unit_unknown
FROM population p JOIN jobs j ON j.id = p.id
