#!/usr/bin/env python3
"""
Fetch 1-2 sample rows from key tables in ADS_DATASET and GA4_DATASET for Copilot knowledge base.
Writes bigquery_schema/copilot_samples.json. Run periodically (e.g. weekly) to refresh samples.

Uses .env: BQ_PROJECT, BQ_SOURCE_PROJECT (optional), ADS_DATASET, GA4_DATASET, BQ_LOCATION (optional).

Usage (from repo root):
  python scripts/copilot_fetch_samples.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env from repo root if present."""
    repo_root = Path(__file__).resolve().parents[1]
    env_file = repo_root / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"").strip()
                if k and v and k not in os.environ:
                    os.environ[k] = v


def _serialize_value(v) -> any:
    """Make a value JSON-serializable (date, timestamp, etc.)."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def main() -> int:
    _load_dotenv()
    project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
    source_project = os.environ.get("BQ_SOURCE_PROJECT") or project
    ads_dataset = os.environ.get("ADS_DATASET", "146568")
    ga4_dataset = os.environ.get("GA4_DATASET", "analytics_444259275")
    location = os.environ.get("BQ_LOCATION", "europe-north2")

    try:
        from google.cloud import bigquery
    except ImportError:
        print("google-cloud-bigquery is not installed. pip install google-cloud-bigquery", file=sys.stderr)
        return 1

    client = bigquery.Client(project=source_project, location=location)
    out: dict[str, dict[str, list]] = {}

    # Ads: one key table (account-level stats)
    ads_table = "ads_AccountBasicStats_4221201460"
    full_ads = f"`{project}.{ads_dataset}.{ads_table}`"
    try:
        job = client.query(f"SELECT * FROM {full_ads} LIMIT 2")
        rows = list(job.result())
        serialized = []
        for row in rows:
            serialized.append({k: _serialize_value(v) for k, v in row.items()})
        out.setdefault(ads_dataset, {})[ads_table] = serialized
    except Exception as e:
        print(f"Ads table {ads_table}: {e}", file=sys.stderr)
        out.setdefault(ads_dataset, {})[ads_table] = []

    # GA4: first events_* table found (e.g. events_20260221)
    try:
        dataset_ref = f"{source_project}.{ga4_dataset}"
        tables = list(client.list_tables(dataset_ref))
        events_tables = sorted([t.table_id for t in tables if t.table_id.startswith("events_") and not t.table_id.startswith("events_intraday_")])
        ga4_table = events_tables[0] if events_tables else None
    except Exception as e:
        print(f"GA4 list tables: {e}", file=sys.stderr)
        ga4_table = None

    if ga4_table:
        full_ga4 = f"`{source_project}.{ga4_dataset}.{ga4_table}`"
        try:
            job = client.query(f"SELECT * FROM {full_ga4} LIMIT 2")
            rows = list(job.result())
            serialized = []
            for row in rows:
                serialized.append({k: _serialize_value(v) for k, v in row.items()})
            out.setdefault(ga4_dataset, {})[f"events_sample_{ga4_table}"] = serialized
        except Exception as e:
            print(f"GA4 table {ga4_table}: {e}", file=sys.stderr)
            out.setdefault(ga4_dataset, {})[f"events_sample_{ga4_table}"] = []

    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "bigquery_schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    samples_path = schema_dir / "copilot_samples.json"
    samples_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {samples_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
