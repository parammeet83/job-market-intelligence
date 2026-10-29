-- Skill share among currently active listings, analyst toolkit only.
-- Denominator: distinct active listings (not observation rows).
SELECT skill_name, listings, eligible_listings, share_pct
FROM v_skill_share_active
WHERE skill_slug IN ('sql', 'python', 'excel', 'power-bi', 'tableau')
ORDER BY share_pct DESC;
