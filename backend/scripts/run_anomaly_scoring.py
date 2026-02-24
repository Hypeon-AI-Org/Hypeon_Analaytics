#!/usr/bin/env python3
"""Run BQ ML anomaly scoring: forecast vs actual, write to anomaly_flags. Env: BQ_PROJECT, ANALYTICS_DATASET."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

BQ_PROJECT = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
ANALYTICS_DATASET = os.environ.get("ANALYTICS_DATASET", "analytics")

QUERY = f"""
INSERT INTO `{BQ_PROJECT}.{ANALYTICS_DATASET}.anomaly_flags` (client_id, campaign_id, date, is_anomaly, anomaly_score, revenue, predicted_revenue, created_at)
WITH forecast AS (
  SELECT campaign_key, forecast_timestamp AS date, forecast_value AS predicted_revenue
  FROM ML.FORECAST(MODEL `{BQ_PROJECT}.{ANALYTICS_DATASET}.revenue_anomaly_model`, STRUCT(3 AS horizon))
),
actual AS (
  SELECT client_id, campaign_id, date, SUM(revenue) AS revenue
  FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily`
  WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
  GROUP BY 1, 2, 3
),
joined AS (
  SELECT
    CAST(SPLIT(f.campaign_key, '_')[OFFSET(0)] AS INT64) AS client_id,
    COALESCE(REGEXP_EXTRACT(f.campaign_key, r'_([^_]*)$'), '') AS campaign_id,
    f.date,
    a.revenue,
    f.predicted_revenue,
    ABS(COALESCE(a.revenue, 0) - COALESCE(f.predicted_revenue, 0)) AS residual
  FROM forecast f
  LEFT JOIN actual a ON CONCAT(CAST(a.client_id AS STRING), '_', COALESCE(a.campaign_id, '')) = f.campaign_key AND a.date = f.date
),
stats AS (SELECT STDDEV(residual) AS sd FROM joined)
SELECT
  j.client_id,
  j.campaign_id,
  j.date,
  (j.residual > 2 * COALESCE(s.sd, 0)) AS is_anomaly,
  SAFE_DIVIDE(j.residual, NULLIF(s.sd, 0)) AS anomaly_score,
  j.revenue,
  j.predicted_revenue,
  CURRENT_TIMESTAMP() AS created_at
FROM joined j
CROSS JOIN stats s
"""


def main() -> int:
    try:
        from google.cloud import bigquery
    except ImportError:
        print("pip install google-cloud-bigquery", file=sys.stderr)
        return 1
    client = bigquery.Client(project=BQ_PROJECT)
    client.query(QUERY).result()
    print("Anomaly scoring completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
