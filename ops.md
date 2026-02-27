# Ops runbooks (HypeOn Analytics V1)

## Incidents

### Insights not appearing

1. Check unified table: `SELECT COUNT(*), MAX(date) FROM project.analytics.marketing_performance_daily`.
2. If empty or stale, run `backend/scripts/run_unified_table.py` or trigger the DAG task `run_unified_table`.
3. If using `analytics_insights`: verify the table has rows: `SELECT * FROM project.analytics.analytics_insights LIMIT 10`. Insights are populated from your marts/ETL; there is no automated agents pipeline.

### API 5xx

1. Cloud Run: check logs in Cloud Logging for the service; look for BigQuery or dependency errors.
2. Env: confirm `BQ_PROJECT`, `ANALYTICS_DATASET`, `GOOGLE_APPLICATION_CREDENTIALS` (or workload identity) are set.
3. BigQuery: confirm datasets and tables exist and the service account has `roles/bigquery.dataEditor` and `roles/bigquery.jobUser`.

### DAG failures

1. In Cloud Composer, open the DAG run and check task logs.
2. If `run_unified_table` fails: ensure `HYPEON_REPO_PATH` points to a path that contains `backend/scripts/run_unified_table.py` (e.g. repo synced to GCS and mounted).
3. If Python fails: ensure the Composer environment has dependencies (e.g. install via pip in the environment or use a custom Docker image).

## Alerting

- See [monitoring/README.md](monitoring/README.md) for the alert rule (e.g. > 10 HIGH severity insights per client per hour) and PagerDuty/email setup.

## Scaling

- **Cloud Run:** Increase max instances and CPU/memory if the API is slow under load; consider min instances > 0 for critical paths.
- **BigQuery:** Queries are already scoped by `client_id` and use partitioned/clustered tables; avoid ad-hoc full scans.
- **Composer:** Increase worker count if DAG tasks are often queued; ensure worker resources are sufficient for the Python scripts.

## Secrets

- Do not commit credentials. Use Secret Manager and reference in Cloud Run or Composer (e.g. mount as volume or env).
- Rotate service account keys periodically; prefer workload identity where possible.
