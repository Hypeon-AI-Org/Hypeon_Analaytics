#!/usr/bin/env python3
"""
List BigQuery datasets that are safe to DROP (derived only).
NEVER suggests dropping ADS_DATASET or GA4_DATASET from .env (146568, analytics_444259275),
or any dataset starting with analytics_* or raw_*.
Outputs DROP SCHEMA statements for review; user runs them manually.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env from repo root
_repo_root = Path(__file__).resolve().parents[2]
_env = _repo_root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

# Protected dataset IDs (from .env lines 18-19)
ADS_DATASET = (os.environ.get("ADS_DATASET") or "146568").strip()
GA4_DATASET = (os.environ.get("GA4_DATASET") or "analytics_444259275").strip()
BQ_PROJECT = os.environ.get("BQ_PROJECT", "hypeon-ai-prod")


def is_protected(dataset_id: str) -> bool:
    """True if this dataset must never be dropped."""
    d = dataset_id.strip().lower()
    if d == ADS_DATASET.lower():
        return True
    if d == GA4_DATASET.lower():
        return True
    if d.startswith("analytics_"):
        return True
    if d.startswith("raw_"):
        return True
    return False


def main() -> None:
    try:
        from google.cloud import bigquery
    except ImportError:
        print("Install: pip install google-cloud-bigquery python-dotenv", file=sys.stderr)
        sys.exit(1)

    client = bigquery.Client(project=BQ_PROJECT)
    project = client.project
    to_drop = []
    for ds in client.list_datasets():
        ds_id = ds.dataset_id
        if is_protected(ds_id):
            print(f"KEEP (protected): {project}.{ds_id}", file=sys.stderr)
            continue
        to_drop.append(ds_id)

    print(f"-- Safe to DROP (review before running). Project: {project}")
    print(f"-- Protected: ADS_DATASET={ADS_DATASET}, GA4_DATASET={GA4_DATASET}, analytics_*, raw_*")
    for ds_id in sorted(to_drop):
        print(f"DROP SCHEMA IF EXISTS `{project}.{ds_id}` CASCADE;")
    if not to_drop:
        print("-- No derived datasets to drop.")


if __name__ == "__main__":
    main()
