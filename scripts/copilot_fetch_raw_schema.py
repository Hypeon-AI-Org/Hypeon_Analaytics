#!/usr/bin/env python3
"""
Generate raw_copilot_schema.json for Copilot run_sql_raw fallback.
Fetches schema + 1-2 sample rows from GA4 events_* and Ads ads_AccountBasicStats_* tables.
Run periodically (e.g. weekly) so the Copilot has up-to-date raw schema and query hints.

Uses .env: BQ_PROJECT, BQ_SOURCE_PROJECT (optional), ADS_DATASET, GA4_DATASET, BQ_LOCATION.

Usage (from repo root):
  python scripts/copilot_fetch_raw_schema.py
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
    """Make a value JSON-serializable."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _field_to_dict(field) -> dict:
    """Convert BigQuery SchemaField to a serializable dict."""
    d = {"name": field.name, "type": field.field_type, "mode": getattr(field, "mode") or "NULLABLE"}
    if getattr(field, "fields", None):
        d["fields"] = [_field_to_dict(f) for f in field.fields]
    return d


def _truncate_sample_row(row: dict, max_value_len: int = 200) -> dict:
    """Truncate long values in a sample row to keep JSON small."""
    out = {}
    for k, v in row.items():
        if v is not None and isinstance(v, str) and len(v) > max_value_len:
            out[k] = v[:max_value_len] + "..."
        else:
            out[k] = _serialize_value(v)
    return out


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
    out: dict = {
        "project": source_project,
        "hints": (
            "GA4 events_*: Use UNNEST(event_params) for event_params; UNNEST(items) for items. "
            "Always filter by event_date (e.g. WHERE event_date >= '2025-01-01') to limit scan. "
            "Ads tables: filter by segments_date when relevant."
        ),
        "datasets": {},
    }

    # GA4: first events_* table
    try:
        dataset_ref = f"{source_project}.{ga4_dataset}"
        tables = list(client.list_tables(dataset_ref))
        events_tables = sorted(
            [t.table_id for t in tables if t.table_id.startswith("events_") and not t.table_id.startswith("events_intraday_")]
        )
        ga4_table = events_tables[0] if events_tables else None
    except Exception as e:
        print(f"GA4 list tables: {e}", file=sys.stderr)
        ga4_table = None

    if ga4_table:
        full_ga4 = f"{source_project}.{ga4_dataset}.{ga4_table}"
        try:
            table = client.get_table(full_ga4)
            schema = [_field_to_dict(f) for f in table.schema]
            job = client.query(f"SELECT * FROM `{full_ga4}` LIMIT 2")
            rows = list(job.result())
            sample_rows = [_truncate_sample_row(dict(r.items())) for r in rows]
            out["datasets"].setdefault(ga4_dataset, {}).setdefault("tables", {})[ga4_table] = {
                "schema": schema,
                "sample_rows": sample_rows,
            }
        except Exception as e:
            print(f"GA4 table {ga4_table}: {e}", file=sys.stderr)
            out["datasets"].setdefault(ga4_dataset, {}).setdefault("tables", {})[ga4_table] = {"schema": [], "sample_rows": [], "error": str(e)[:200]}

    # Ads: one allowlisted table
    ads_table = "ads_AccountBasicStats_4221201460"
    full_ads = f"{source_project}.{ads_dataset}.{ads_table}"
    try:
        table = client.get_table(full_ads)
        schema = [_field_to_dict(f) for f in table.schema]
        job = client.query(f"SELECT * FROM `{full_ads}` LIMIT 2")
        rows = list(job.result())
        sample_rows = [_truncate_sample_row(dict(r.items())) for r in rows]
        out["datasets"].setdefault(ads_dataset, {}).setdefault("tables", {})[ads_table] = {
            "schema": schema,
            "sample_rows": sample_rows,
        }
    except Exception as e:
        print(f"Ads table {ads_table}: {e}", file=sys.stderr)
        out["datasets"].setdefault(ads_dataset, {}).setdefault("tables", {})[ads_table] = {"schema": [], "sample_rows": [], "error": str(e)[:200]}

    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "bigquery_schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    out_path = schema_dir / "raw_copilot_schema.json"
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
