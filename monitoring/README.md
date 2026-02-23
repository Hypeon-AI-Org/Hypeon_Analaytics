# Monitoring and alerting (HypeOn Analytics V1)

## Cloud Logging

- Backend (Cloud Run): logs are automatically sent to Cloud Logging. Use structured logging (JSON) for easier querying.
- Recommended fields: `severity`, `message`, `client_id`, `insight_id`, `trace`.

## Alert rule (example)

**Condition:** More than 10 HIGH-severity insights for a single client within 1 hour.

- **Metric:** Count of `analytics_insights` rows where `status = 'new'` and `insight_type` in high-severity types (e.g. `waste_zero_revenue`, `roas_decline`, `anomaly`), grouped by `client_id`, in a 1-hour window.
- **Threshold:** > 10.
- **Action:** Notify PagerDuty or send email (configure in Cloud Monitoring notification channels).

### Cloud Monitoring config (stub)

1. Create a log-based metric:
   - Filter: `resource.type="cloud_run_revision" AND jsonPayload.insight_id!="" AND jsonPayload.severity="HIGH"`
   - Metric: count per 1 hour, group by `jsonPayload.client_id`.

2. Create an alert policy:
   - Condition: metric above 10.
   - Notification channel: PagerDuty integration or email.

### PagerDuty

- In GCP Console → Monitoring → Alerting → Edit notification channels, add PagerDuty and link your service key.
- In the alert policy, add the PagerDuty channel as a notification.

### Email

- Add an email notification channel in Cloud Monitoring and attach it to the alert policy.

## Scaling tips

- Cloud Run: set min instances to 0 for cost savings; increase max instances and CPU/memory if latency increases.
- BigQuery: use partitioned and clustered tables (already in place); avoid full table scans in agents.
- Airflow/Composer: scale worker count if DAGs are queued.
