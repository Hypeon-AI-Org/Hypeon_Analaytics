# BigQuery SQL (HypeOn Analytics V1)

## Overview

- **Unified table**: `marketing_performance_daily` — one row per (client_id, date, channel, campaign_id, ad_group_id, device) with spend, clicks, impressions, sessions, conversions, revenue, roas, cpa, ctr, conversion_rate, and 7d/28d rolling baselines.
- **Decision Store**: `analytics_insights` table + `analytics_recommendations` view.

## Environment

Set before running scripts or DAGs:

- `BQ_PROJECT` — GCP project (e.g. braided-verve-459208-i6)
- `ANALYTICS_DATASET` — dataset for unified table and insights (e.g. analytics)
- `ADS_DATASET` — Google Ads dataset (e.g. 146568)
- `GA4_DATASET` — GA4 dataset (e.g. analytics_444259275)
- `GOOGLE_APPLICATION_CREDENTIALS` — path to service account key JSON

## Running

- Unified table: `python backend/scripts/run_unified_table.py` (or invoke via Airflow/Cloud Run).
- Decision Store: `python backend/scripts/run_decision_store.py`.

## Example test query (unified table)

After the unified table job has run:

```sql
SELECT client_id, date, channel, campaign_id, spend, revenue, roas
FROM `your_project.your_analytics_dataset.marketing_performance_daily`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
ORDER BY date DESC
LIMIT 10;
```

## Schema: analytics_insights

| Field | Type | Description |
|-------|------|-------------|
| insight_id | STRING | Deterministic id (hash of rule + entity + period) |
| client_id | INT64 | Tenant/client |
| entity_type | STRING | e.g. campaign, ad_group, channel |
| entity_id | STRING | Id of the entity |
| insight_type | STRING | e.g. waste_zero_revenue, roas_decline, anomaly |
| summary | STRING | Short summary |
| explanation | STRING | Detailed explanation |
| recommendation | STRING | Recommended action |
| expected_impact | STRUCT<metric, estimate, units> | Expected impact of action |
| confidence | FLOAT64 | 0–1 |
| evidence | ARRAY<STRUCT<metric, value, baseline, period>> | Supporting metrics |
| detected_by | ARRAY<STRING> | Rule or agent names |
| status | STRING | new, reviewed, applied, rejected |
| created_at | TIMESTAMP | Creation time |
| applied_at | TIMESTAMP | When applied (if any) |
| history | STRING | Audit / history blob |

## Schema: analytics_recommendations

View over `analytics_insights` where `status IN ('new', 'reviewed')` for actionable items only.
