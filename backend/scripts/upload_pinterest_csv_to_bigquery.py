#!/usr/bin/env python3
"""
Upload Pinterest metrics CSV to BigQuery.
Reads the CSV, normalizes column names, and loads into a BigQuery table.

Usage (from repo root):
  python -m backend.scripts.upload_pinterest_csv_to_bigquery
  # uses data/metrics_2025-01-01_to_2026-03-08.csv, project/dataset/table from env or defaults

  python -m backend.scripts.upload_pinterest_csv_to_bigquery path/to/file.csv --dataset pinterest --table my_table
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass


def _bq_safe_name(name: str) -> str:
    """Convert column name to BigQuery-safe (letters, numbers, underscore)."""
    s = re.sub(r"[^\w\s]", "", name)
    s = re.sub(r"\s+", "_", s.strip())
    return s or "unnamed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload Pinterest metrics CSV to BigQuery")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=str(ROOT / "data" / "metrics_2025-01-01_to_2026-03-08.csv"),
        help="Path to CSV file",
    )
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("BQ_PROJECT") or "hypeon-ai-prod", help="GCP project ID")
    parser.add_argument("--dataset", default=os.environ.get("PINTEREST_BQ_DATASET") or "pinterest", help="BigQuery dataset name")
    parser.add_argument("--table", default="metrics_2025_01_01_to_2026_03_08", help="BigQuery table name")
    parser.add_argument("--location", default=os.environ.get("BQ_LOCATION") or "europe-north2", help="Dataset location")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.is_file():
        print("Error: CSV file not found:", csv_path, file=sys.stderr)
        return 1

    import pandas as pd
    from google.cloud import bigquery

    # Read CSV (Pinterest uses comma thousands separator in numbers)
    df = pd.read_csv(csv_path, thousands=",", encoding="utf-8")
    if df.empty:
        print("Error: CSV is empty", file=sys.stderr)
        return 1

    # Normalize column names for BigQuery
    df.columns = [_bq_safe_name(str(c)) for c in df.columns]

    # Ensure numeric columns (BigQuery will infer from pandas dtypes)
    numeric_cols = [
        "Spend", "Impressions", "Pin_clicks", "Outbound_clicks",
        "Total_CPA_Checkout", "Total_ROAS_Checkout", "Total_conversions_Checkout",
        "Total_order_value_Checkout", "Total_conversion_rate_Checkout", "Daily_budget",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    client = bigquery.Client(project=args.project, location=args.location)
    dataset_ref = f"{args.project}.{args.dataset}"
    table_ref = f"{dataset_ref}.{args.table}"

    # Create dataset if not exists
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        from google.cloud.bigquery import Dataset
        dataset = Dataset(dataset_ref)
        dataset.location = args.location
        client.create_dataset(dataset, exists_ok=True)
        print("Created dataset:", dataset_ref)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )
    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    print("Loaded", len(df), "rows into", table_ref)
    return 0


if __name__ == "__main__":
    sys.exit(main())
