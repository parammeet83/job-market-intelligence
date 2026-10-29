-- Employers with the most listings within POPULATION(:start, :end). Listings without a
-- company name are excluded from this ranking.
WITH population AS ({{population(start, end)}})
SELECT j.company AS label, count(*) AS listings
FROM population p JOIN jobs j ON j.id = p.id
WHERE j.company IS NOT NULL
GROUP BY 1
ORDER BY listings DESC, label
LIMIT :limit
