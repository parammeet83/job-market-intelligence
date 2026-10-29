-- Daily listing activity between :start and :end for the filtered population.
-- listings_observed: distinct listings with an observation that day.
-- listings_first_seen: of those, listings first observed by this pipeline that day.
-- reported_closed: listings the source explicitly reported as closed that day.
SELECT
    o.observation_date AS date,
    count(DISTINCT o.job_id) AS listings_observed,
    count(DISTINCT o.job_id) FILTER (
        WHERE (j.first_seen_at AT TIME ZONE 'UTC')::date = o.observation_date
    ) AS listings_first_seen,
    count(DISTINCT o.job_id) FILTER (WHERE o.observed_status = 'expired') AS reported_closed
FROM job_observations o
JOIN jobs j ON j.id = o.job_id
WHERE o.observation_date BETWEEN :start AND :end
  AND {{job_filters}}
GROUP BY o.observation_date
ORDER BY o.observation_date
