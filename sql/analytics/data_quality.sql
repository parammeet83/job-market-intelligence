-- Data-quality results for one run (latest finished run when :run_id is NULL).
SELECT q.run_id, q.source_id, q.check_name, q.outcome, q.failed_count, q.details, q.created_at
FROM data_quality_results q
WHERE q.run_id = COALESCE(
    CAST(:run_id AS bigint),
    (SELECT id FROM ingestion_runs WHERE finished_at IS NOT NULL ORDER BY started_at DESC LIMIT 1)
)
ORDER BY q.source_id NULLS LAST, q.check_name
