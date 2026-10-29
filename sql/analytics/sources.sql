-- Source registry with health/freshness and record counts (safe fields only).
SELECT h.source_id, h.name, h.enabled, h.access_method, h.homepage_url, h.attribution,
       h.allow_row_export, h.disabled_reason, h.last_attempt_at, h.last_success_at,
       h.last_fetch_complete, h.last_record_count, h.last_error_at, h.last_error_summary,
       h.jobs_total, h.jobs_active,
       (SELECT count(*) FROM job_observations o WHERE o.source_id = h.source_id)
           AS observations_total,
       (SELECT min(first_seen_at) FROM jobs j WHERE j.source_id = h.source_id) AS first_seen_at
FROM v_source_health h
ORDER BY h.enabled DESC, h.name
