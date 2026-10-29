-- Most frequent original location strings as published by the sources.
WITH population AS ({{population(start, end)}})
SELECT COALESCE(j.location_original, '(not stated)') AS label, count(*) AS listings
FROM population p JOIN jobs j ON j.id = p.id
GROUP BY 1
ORDER BY listings DESC, label
LIMIT :limit
