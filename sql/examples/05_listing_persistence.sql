-- How long listings stay visible, split by evidence for disappearance.
SELECT status,
       count(*) AS listings,
       round(avg(EXTRACT(EPOCH FROM (last_seen_at - first_seen_at)) / 86400)::numeric, 1)
           AS avg_days_observed
FROM v_jobs_public
GROUP BY status;
