-- Seniority distribution (source-provided level when available, else title keywords).
WITH population AS ({{population(start, end)}})
SELECT COALESCE(j.seniority, 'unknown') AS label, count(*) AS listings
FROM population p JOIN jobs j ON j.id = p.id
GROUP BY 1
ORDER BY listings DESC, label
