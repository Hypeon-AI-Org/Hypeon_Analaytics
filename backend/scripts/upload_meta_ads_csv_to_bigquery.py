#!/usr/bin/env python3
"""
Upload Meta Ads (Facebook/Instagram) CSV files to BigQuery meta_ads dataset.
Reads CSVs, normalizes column names, and loads each as a table.

Usage (from repo root):
  python -m backend.scripts.upload_meta_ads_csv_to_bigquery
  # uploads all three Wallpassion Meta Ads CSVs to meta_ads dataset

  python -m backend.scripts.upload_meta_ads_csv_to_bigquery path/to/file.csv --table my_table
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


# Default: upload these three files into meta_ads with these table names
DEFAULT_FILES = [
    (ROOT / "data" / "Wallpassion-Ad-sets-1-Jan-2025-8-Mar-2026.csv", "ad_sets"),
    (ROOT / "data" / "Wallpassion-Campaigns-1-Jan-2025-8-Mar-2026.csv", "campaigns"),
    (ROOT / "data" / "Wallpassion-Ads-1-Jan-2025-8-Mar-2026.csv", "ads"),
]


def upload_one(
    csv_path: Path,
    table_name: str,
    project: str,
    dataset: str,
    location: str,
) -> int:
    """Upload a single CSV to BigQuery. Returns 0 on success, 1 on error."""
    import pandas as pd
    from google.cloud import bigquery

    if not csv_path.is_file():
        print("Error: CSV not found:", csv_path, file=sys.stderr)
        return 1

    df = pd.read_csv(csv_path, thousands=",", encoding="utf-8")
    if df.empty:
        print("Error: CSV is empty:", csv_path, file=sys.stderr)
        return 1

    df.columns = [_bq_safe_name(str(c)) for c in df.columns]

    client = bigquery.Client(project=project, location=location)
    dataset_ref = f"{project}.{dataset}"
    table_ref = f"{dataset_ref}.{table_name}"

    try:
        client.get_dataset(dataset_ref)
    except Exception:
        from google.cloud.bigquery import Dataset
        ds = Dataset(dataset_ref)
        ds.location = location
        client.create_dataset(ds, exists_ok=True)
        print("Created dataset:", dataset_ref)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )
    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    print("Loaded", len(df), "rows into", table_ref)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload Meta Ads CSVs to BigQuery meta_ads dataset")
    parser.add_argument(
        "csv_path",
        nargs="?",
        help="Single CSV path (optional; if omitted, uploads all three default files)",
    )
    parser.add_argument("--table", help="Table name (required if csv_path is given)")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("BQ_PROJECT") or "hypeon-ai-prod", help="GCP project ID")
    parser.add_argument("--dataset", default="meta_ads", help="BigQuery dataset name")
    parser.add_argument("--location", default=os.environ.get("BQ_LOCATION") or "europe-north2", help="Dataset location")
    args = parser.parse_args()

    if args.csv_path and args.table:
        # Single file
        pairs = [(Path(args.csv_path), args.table)]
    elif args.csv_path or args.table:
        print("Error: provide both csv_path and --table for single-file upload", file=sys.stderr)
        return 1
    else:
        pairs = [(p, t) for p, t in DEFAULT_FILES]

    failed = 0
    for csv_path, table_name in pairs:
        if upload_one(csv_path, table_name, args.project, args.dataset, args.location) != 0:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
