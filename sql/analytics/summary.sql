-- Overview KPIs.
-- jobs_active: listings whose latest evidence says active (seen in the latest complete feed or
--   confirmed active by the source's status API). Not filtered by period.
-- listings_in_period: distinct listings observed between :start and :end.
-- new_in_period: listings FIRST OBSERVED BY THIS PIPELINE in the period (not publication date).
-- skills_identified_active: distinct dictionary skills found in currently active listings.
WITH population AS ({{population(start, end)}})
SELECT
    (SELECT count(*) FROM jobs) AS jobs_total,
    (SELECT count(*) FROM jobs WHERE status = 'active') AS jobs_active,
    (SELECT count(*) FROM jobs WHERE status = 'unconfirmed') AS jobs_unconfirmed,
    (SELECT count(*) FROM jobs WHERE status = 'expired') AS jobs_expired,
    (SELECT count(*) FROM population) AS listings_in_period,
    (SELECT count(*) FROM jobs j JOIN population p ON p.id = j.id
       WHERE (j.first_seen_at AT TIME ZONE 'UTC')::date BETWEEN :start AND :end) AS new_in_period,
    (SELECT count(*) FROM job_observations) AS observations_total,
    (SELECT count(DISTINCT v.skill_slug) FROM v_job_skills_current v
       JOIN jobs j ON j.id = v.job_id WHERE j.status = 'active') AS skills_identified_active,
    (SELECT count(*) FROM jobs WHERE status = 'active'
       AND (salary_text IS NOT NULL OR salary_min IS NOT NULL OR salary_max IS NOT NULL))
       AS active_with_salary_info,
    (SELECT min(observation_date) FROM job_observations) AS first_observation_date,
    (SELECT max(observation_date) FROM job_observations) AS last_observation_date
