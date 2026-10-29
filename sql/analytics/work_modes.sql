-- Remote / hybrid / on-site distribution with the basis of the classification:
-- text = explicit wording in the listing; source_default = the board lists remote jobs only.
WITH population AS ({{population(start, end)}})
SELECT COALESCE(j.work_mode, 'unknown') AS work_mode,
       COALESCE(j.work_mode_basis, 'none') AS basis,
       count(*) AS listings
FROM population p JOIN jobs j ON j.id = p.id
GROUP BY 1, 2
ORDER BY listings DESC
