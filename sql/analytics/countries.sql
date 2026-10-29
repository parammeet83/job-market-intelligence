-- Listings by normalized country. 'Unspecified' covers worldwide, multi-country and
-- unresolvable location strings: it is NOT a country.
WITH population AS ({{population(start, end)}})
SELECT COALESCE(j.country, 'Unspecified') AS label, count(*) AS listings
FROM population p JOIN jobs j ON j.id = p.id
GROUP BY 1
ORDER BY listings DESC, label
