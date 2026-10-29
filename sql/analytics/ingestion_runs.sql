-- Ingestion audit history with data-quality outcome counts per run.
SELECT r.id, r.started_at, r.finished_at, r.trigger, r.status, r.skills_dictionary_version,
       r.sources_attempted, r.sources_succeeded, r.records_fetched, r.records_valid,
       r.records_invalid, r.records_out_of_scope, r.duplicates, r.jobs_inserted, r.jobs_updated,
       r.observations_written, r.status_checks, r.jobs_marked_expired,
       r.jobs_marked_unconfirmed, r.error_count, r.error_summary,
       count(q.id) FILTER (WHERE q.outcome = 'warn') AS quality_warnings,
       count(q.id) FILTER (WHERE q.outcome = 'fail') AS quality_failures
FROM ingestion_runs r
LEFT JOIN data_quality_results q ON q.run_id = r.id
GROUP BY r.id
ORDER BY r.started_at DESC
LIMIT :limit
