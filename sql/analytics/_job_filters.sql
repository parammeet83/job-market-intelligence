-- Shared job filters (alias `j` = jobs). NULL parameter = no filter.
-- Unclassified roles and unresolved countries are addressable by their display labels.
    (CAST(:source AS text) IS NULL OR j.source_id = :source)
AND (CAST(:role AS text) IS NULL OR COALESCE(j.role_category, 'Unclassified') = :role)
AND (CAST(:country AS text) IS NULL OR COALESCE(j.country, 'Unspecified') = :country)
AND (CAST(:work_mode AS text) IS NULL OR j.work_mode = :work_mode)
