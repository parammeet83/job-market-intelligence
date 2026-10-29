-- Source coverage: listings per source and role in POPULATION(:start, :end), with how many
-- could be resolved to a single country.
WITH population AS ({{population(start, end)}})
SELECT j.source_id, COALESCE(j.role_category, 'Unclassified') AS role, count(*) AS listings,
       count(*) FILTER (WHERE j.country IS NOT NULL) AS with_country
FROM population p JOIN jobs j ON j.id = p.id
GROUP BY 1, 2
ORDER BY 1, listings DESC
