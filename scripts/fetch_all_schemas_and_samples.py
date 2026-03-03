#!/usr/bin/env python3
"""
Fetch schema and sample rows for every table in every dataset we have access to.
Uses .env: BQ_PROJECT, BQ_SOURCE_PROJECT, MARTS_DATASET, MARTS_ADS_DATASET,
GA4_DATASET, ADS_DATASET, BQ_LOCATION, BQ_LOCATION_ADS.

Output: bigquery_schema/all_schemas_and_samples.json

Usage (from repo root):
  python scripts/fetch_all_schemas_and_samples.py
"""
from __future__ import annotations

import json
from typing import Any
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _load_dotenv() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_file = repo_root / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip("'\"").strip()
            if k and v and k not in os.environ:
                os.environ[k] = v


def _serialize_value(v) -> Any:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _field_to_dict(field) -> dict:
    d = {"name": field.name, "type": field.field_type, "mode": getattr(field, "mode") or "NULLABLE"}
    if getattr(field, "fields", None):
        d["fields"] = [_field_to_dict(f) for f in field.fields]
    return d


def _sample_row_dict(row, max_value_len: int = 300) -> dict:
    out = {}
    for k, v in row.items():
        val = _serialize_value(v)
        if isinstance(val, str) and len(val) > max_value_len:
            val = val[:max_value_len] + "..."
        out[k] = val
    return out


def fetch_dataset(
    client,
    project: str,
    dataset_id: str,
    sample_limit: int = 3,
    ga4_events_max: int | None = 10,
) -> dict:
    """Fetch schema + sample rows for every table in the dataset. Returns { tables: { table_id: { schema, sample_rows, error? } } }."""
    full_ref = f"{project}.{dataset_id}"
    result = {"project": project, "dataset": dataset_id, "tables": {}}
    try:
        tables = list(client.list_tables(full_ref))
        table_ids = sorted([t.table_id for t in tables])
    except Exception as e:
        result["error"] = str(e)[:500]
        return result

    # For GA4, optionally limit events_* to avoid hundreds of tables
    if ga4_events_max is not None and dataset_id == os.environ.get("GA4_DATASET", ""):
        events_tables = [t for t in table_ids if t.startswith("events_") and not t.startswith("events_intraday_")]
        other_tables = [t for t in table_ids if t not in events_tables]
        if len(events_tables) > ga4_events_max:
            events_tables = sorted(events_tables)[-ga4_events_max:]  # most recent N by name
        table_ids = other_tables + events_tables

    for table_id in table_ids:
        full_table = f"`{project}.{dataset_id}.{table_id}`"
        entry = {"schema": [], "sample_rows": []}
        try:
            table = client.get_table(f"{project}.{dataset_id}.{table_id}")
            entry["schema"] = [_field_to_dict(f) for f in table.schema]
            job = client.query(f"SELECT * FROM {full_table} LIMIT {sample_limit}")
            rows = list(job.result())
            entry["sample_rows"] = [_sample_row_dict(dict(r.items())) for r in rows]
        except Exception as e:
            entry["error"] = str(e)[:300]
        result["tables"][table_id] = entry
        print(f"  {dataset_id}.{table_id}: {len(entry['schema'])} cols, {len(entry['sample_rows'])} sample rows")

    return result


def main() -> int:
    _load_dotenv()
    try:
        from google.cloud import bigquery
    except ImportError:
        print("pip install google-cloud-bigquery", file=sys.stderr)
        return 1

    project = os.environ.get("BQ_PROJECT", "hypeon-ai-prod")
    source_project = os.environ.get("BQ_SOURCE_PROJECT") or project
    location = os.environ.get("BQ_LOCATION", "europe-north2")
    location_ads = os.environ.get("BQ_LOCATION_ADS", "EU")
    marts_ds = os.environ.get("MARTS_DATASET", "hypeon_marts")
    marts_ads_ds = os.environ.get("MARTS_ADS_DATASET", "hypeon_marts_ads")
    ga4_ds = os.environ.get("GA4_DATASET", "analytics_444259275")
    ads_ds = os.environ.get("ADS_DATASET", "146568")

    # (project, dataset_id, location)
    datasets_config = [
        (project, marts_ds, location),
        (project, marts_ads_ds, location_ads),
        (source_project, ga4_ds, location),
        (source_project, ads_ds, location_ads),
    ]

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "bq_project": project,
        "bq_source_project": source_project,
        "datasets": {},
    }

    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "bigquery_schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    out_path = schema_dir / "all_schemas_and_samples.json"

    for proj, dataset_id, loc in datasets_config:
        print(f"Fetching {proj}.{dataset_id} (location={loc}) ...")
        client = bigquery.Client(project=proj, location=loc)
        ga4_max = 10 if dataset_id == ga4_ds else None
        out["datasets"][dataset_id] = fetch_dataset(client, proj, dataset_id, sample_limit=3, ga4_events_max=ga4_max)
        if out["datasets"][dataset_id].get("error"):
            print(f"  Dataset error: {out['datasets'][dataset_id]['error']}")
        # Save after each dataset so partial results persist if run is interrupted
        out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        print(f"  Saved {out_path}")

    print(f"Done. Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
