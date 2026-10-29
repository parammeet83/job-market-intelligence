-- Most recent ingestion run that stored data (succeeded or partial).
SELECT id, started_at, finished_at, status, trigger
FROM ingestion_runs
WHERE status IN ('succeeded', 'partial')
ORDER BY started_at DESC
LIMIT 1
