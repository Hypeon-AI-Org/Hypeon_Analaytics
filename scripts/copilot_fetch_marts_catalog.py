#!/usr/bin/env python3
"""
Build copilot_marts_catalog.json: datasets, tables, schema (columns + types), and sample rows
for hypeon_marts and hypeon_marts_ads. The copilot uses this to know what data exists and how
to query it (e.g. item views, traffic from Google).

Uses .env: BQ_PROJECT, MARTS_DATASET, MARTS_ADS_DATASET, BQ_LOCATION, BQ_LOCATION_ADS.

Usage (from repo root):
  python scripts/copilot_fetch_marts_catalog.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
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


def main() -> int:
    _load_dotenv()
    project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
    marts_ds = os.environ.get("MARTS_DATASET", "hypeon_marts")
    marts_ads_ds = os.environ.get("MARTS_ADS_DATASET", "hypeon_marts_ads")
    location = os.environ.get("BQ_LOCATION", "europe-north2")
    location_ads = os.environ.get("BQ_LOCATION_ADS", "EU")

    try:
        from google.cloud import bigquery
    except ImportError:
        print("google-cloud-bigquery is not installed. pip install google-cloud-bigquery", file=sys.stderr)
        return 1

    out = {
        "project": project,
        "hints": (
            "fct_sessions: Use event_name IN ('view_item','view_item_list') for item views; "
            "item_id for product; utm_source for traffic source (e.g. utm_source LIKE '%google%' for 'from Google'). "
            "Always add a date filter to limit scan: WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) (or event_date if the table has it)."
        ),
        "datasets": {},
    }

    for dataset_id, loc in [(marts_ds, location), (marts_ads_ds, location_ads)]:
        client = bigquery.Client(project=project, location=loc)
        full_dataset = f"{project}.{dataset_id}"
        out["datasets"][dataset_id] = {"tables": {}}
        try:
            tables = list(client.list_tables(full_dataset))
            table_ids = sorted([t.table_id for t in tables])
        except Exception as e:
            out["datasets"][dataset_id]["error"] = str(e)[:500]
            continue

        for table_id in table_ids:
            full_id = f"{project}.{dataset_id}.{table_id}"
            entry = {}
            try:
                table = client.get_table(full_id)
                entry["schema"] = [_field_to_dict(f) for f in table.schema]
            except Exception as e:
                entry["error"] = str(e)[:500]
                out["datasets"][dataset_id]["tables"][table_id] = entry
                continue

            try:
                job = client.query(f"SELECT * FROM `{full_id}` LIMIT 2")
                rows = list(job.result())
                entry["sample_rows"] = [{k: _serialize_value(v) for k, v in row.items()} for row in rows]
            except Exception as e:
                entry["sample_rows"] = []
                entry["sample_error"] = str(e)[:200]

            out["datasets"][dataset_id]["tables"][table_id] = entry

    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "bigquery_schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    out_path = schema_dir / "copilot_marts_catalog.json"
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
