#!/usr/bin/env python3
"""
Run the unified marketing_performance_daily table job in BigQuery.
Uses env: BQ_PROJECT, ANALYTICS_DATASET, ADS_DATASET, GA4_DATASET, GOOGLE_APPLICATION_CREDENTIALS.
Invoked by Airflow/Cloud Composer or Cloud Scheduler + Cloud Run job.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend app to path if running from repo root
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BQ_PROJECT = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
ANALYTICS_DATASET = os.environ.get("ANALYTICS_DATASET", "analytics")
ADS_DATASET = os.environ.get("ADS_DATASET", "146568")
GA4_DATASET = os.environ.get("GA4_DATASET", "analytics_444259275")

SQL_FILE = ROOT / "bq_sql" / "create_unified_table.sql"


def main() -> int:
    if not SQL_FILE.exists():
        print(f"SQL file not found: {SQL_FILE}", file=sys.stderr)
        return 1

    sql = SQL_FILE.read_text()
    sql = sql.replace("{BQ_PROJECT}", BQ_PROJECT)
    sql = sql.replace("{ANALYTICS_DATASET}", ANALYTICS_DATASET)
    sql = sql.replace("{ADS_DATASET}", ADS_DATASET)
    sql = sql.replace("{GA4_DATASET}", GA4_DATASET)

    try:
        from google.cloud import bigquery
    except ImportError:
        print("Install google-cloud-bigquery: pip install google-cloud-bigquery", file=sys.stderr)
        return 1

    client = bigquery.Client(project=BQ_PROJECT)
    job = client.query(sql)
    job.result()
    print(f"Created/updated table {BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily")
    return 0


if __name__ == "__main__":
    sys.exit(main())
