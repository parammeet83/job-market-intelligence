-- POPULATION: distinct listings observed (feed or status check) at least once between
-- :start and :end (inclusive, UTC dates) that match the shared filters. This is the
-- denominator for every share/percentage in the period-based analytics.
SELECT DISTINCT j.id
FROM jobs j
JOIN job_observations o ON o.job_id = j.id
WHERE o.observation_date BETWEEN :start AND :end
  AND {{job_filters}}
