-- Source freshness: hours since the last successful fetch.
SELECT source_id, name, enabled, last_success_at,
       round(EXTRACT(EPOCH FROM (now() - last_success_at)) / 3600, 1) AS hours_since_success,
       last_fetch_complete, last_record_count, jobs_active
FROM v_source_health
ORDER BY enabled DESC, source_id;
