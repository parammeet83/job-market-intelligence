-- Listings per role category within POPULATION(:start, :end). Share denominator = population.
WITH population AS ({{population(start, end)}})
SELECT COALESCE(j.role_category, 'Unclassified') AS label, count(*) AS listings
FROM population p JOIN jobs j ON j.id = p.id
GROUP BY 1
ORDER BY listings DESC, label
