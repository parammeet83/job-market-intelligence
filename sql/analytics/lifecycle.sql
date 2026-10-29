-- Persistence of listings within POPULATION(:start, :end): how long listings have been
-- observed and how many are no longer observed, by evidence type:
-- expired = the source explicitly reported the listing closed;
-- unconfirmed = absent from consecutive complete feeds (possible disappearance, not proof).
WITH population AS ({{population(start, end)}})
SELECT
    j.status,
    count(*) AS listings,
    round(avg(EXTRACT(EPOCH FROM (j.last_seen_at - j.first_seen_at)) / 86400.0)::numeric, 1)
        AS avg_days_observed,
    count(*) FILTER (WHERE j.last_seen_at - j.first_seen_at >= interval '7 days')
        AS observed_7_days_or_more
FROM population p JOIN jobs j ON j.id = p.id
GROUP BY j.status
ORDER BY j.status
