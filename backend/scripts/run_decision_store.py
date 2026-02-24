#!/usr/bin/env python3
"""Create Decision Store table and view in BigQuery. Env: BQ_PROJECT, ANALYTICS_DATASET, BQ_LOCATION."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SQL_FILE = ROOT / "bq_sql" / "create_decision_store.sql"
SQL_ENTERPRISE = ROOT / "bq_sql" / "create_decision_store_enterprise.sql"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

BQ_PROJECT = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
ANALYTICS_DATASET = os.environ.get("ANALYTICS_DATASET", "analytics")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "europe-north2")


def main() -> int:
    try:
        from google.cloud import bigquery
    except ImportError:
        print("pip install google-cloud-bigquery", file=sys.stderr)
        return 1
    # Use same location as analytics dataset (unified table) so table exists where pipeline runs
    client = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION)
    # Prefer enterprise schema (has organization_id, insight_hash, priority_score, etc.)
    sql_path = SQL_ENTERPRISE if SQL_ENTERPRISE.exists() else SQL_FILE
    if not sql_path.exists():
        print(f"SQL file not found: {sql_path}", file=sys.stderr)
        return 1
    sql = sql_path.read_text().replace("{BQ_PROJECT}", BQ_PROJECT).replace("{ANALYTICS_DATASET}", ANALYTICS_DATASET)
    # Drop view then table so enterprise schema (or updated schema) applies
    client.query(f"DROP VIEW IF EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_recommendations`").result()
    client.query(f"DROP TABLE IF EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights`").result()
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            client.query(stmt).result()
    print(f"Decision store ready: {BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights")
    return 0


if __name__ == "__main__":
    sys.exit(main())
