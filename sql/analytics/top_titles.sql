-- Most frequent normalized job titles within POPULATION(:start, :end).
WITH population AS ({{population(start, end)}})
SELECT j.title_normalized AS label, count(*) AS listings
FROM population p JOIN jobs j ON j.id = p.id
GROUP BY 1
ORDER BY listings DESC, label
LIMIT :limit
