#!/usr/bin/env python3
"""Create Decision Store table and view in BigQuery. Env: BQ_PROJECT, ANALYTICS_DATASET."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SQL_FILE = ROOT / "bq_sql" / "create_decision_store.sql"

BQ_PROJECT = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
ANALYTICS_DATASET = os.environ.get("ANALYTICS_DATASET", "analytics")


def main() -> int:
    if not SQL_FILE.exists():
        print(f"SQL file not found: {SQL_FILE}", file=sys.stderr)
        return 1
    sql = SQL_FILE.read_text().replace("{BQ_PROJECT}", BQ_PROJECT).replace("{ANALYTICS_DATASET}", ANALYTICS_DATASET)
    try:
        from google.cloud import bigquery
    except ImportError:
        print("pip install google-cloud-bigquery", file=sys.stderr)
        return 1
    client = bigquery.Client(project=BQ_PROJECT)
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            client.query(stmt).result()
    print(f"Decision store ready: {BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights")
    return 0


if __name__ == "__main__":
    sys.exit(main())
