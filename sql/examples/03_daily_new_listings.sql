-- Listings first observed by the pipeline per day and source ("new" = first seen, not published).
SELECT observation_date, source_id, listings_observed, listings_first_seen
FROM v_daily_listing_activity
ORDER BY observation_date DESC, source_id;
