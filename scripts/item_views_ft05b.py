#!/usr/bin/env python3
"""
Script: Views count of Item Id starting with FT05B (from GA4).
  - Total views
  - Views coming from Google (traffic_source.source or session source)
Run from repo root:
  python scripts/item_views_ft05b.py
  ITEM_PREFIX=FT05B python scripts/item_views_ft05b.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root and load .env
_repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_repo_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_repo_root / ".env")
    load_dotenv(Path.cwd() / ".env")
except Exception:
    pass

PREFIX = os.environ.get("ITEM_PREFIX", "FT05B").strip() or "FT05B"

VIEW_ITEM_EVENTS = ("view_item", "view_item_list")


def _get_item_views_from_google(prefix: str) -> dict:
    """Count item views for prefix where traffic came from Google (GA4 traffic_source)."""
    try:
        from google.cloud import bigquery
        from backend.app.clients.bigquery import get_ga4_dataset, _source_project
    except ImportError as e:
        return {"error": str(e), "views_count": None}
    project = _source_project()
    dataset = get_ga4_dataset()
    location = os.environ.get("BQ_LOCATION", "europe-north2")
    table_ref = f"`{project}.{dataset}.events_*`"
    query = f"""
    SELECT COUNT(*) AS views_count
    FROM {table_ref},
    UNNEST(COALESCE(items, [])) AS it
    WHERE event_date IS NOT NULL
      AND event_name IN {VIEW_ITEM_EVENTS}
      AND STARTS_WITH(COALESCE(it.item_id, ''), @prefix)
      AND (
        LOWER(COALESCE(traffic_source.source, '')) LIKE '%google%'
        OR (session_traffic_source_last_click.manual_campaign IS NOT NULL
            AND LOWER(COALESCE(session_traffic_source_last_click.manual_campaign.source, '')) LIKE '%google%')
        OR (session_traffic_source_last_click.cross_channel_campaign IS NOT NULL
            AND LOWER(COALESCE(session_traffic_source_last_click.cross_channel_campaign.source, '')) LIKE '%google%')
      )
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("prefix", "STRING", prefix)],
        maximum_bytes_billed=300 * 1024 * 1024,  # 300 MB (events_* + traffic_source scan)
    )
    try:
        client = bigquery.Client(project=project, location=location)
        job = client.query(query, job_config=job_config)
        rows = list(job.result(timeout=30))
        count = int(rows[0][0]) if rows else 0
        return {"views_count": count, "item_id_prefix": prefix}
    except Exception as e:
        return {"error": str(e)[:300], "views_count": None, "item_id_prefix": prefix}


def main() -> int:
    print("Views count of Item Id starting with", PREFIX, "(from GA4 events_*)")
    print("-" * 55)

    try:
        from backend.app.clients.bigquery import get_item_views_count
    except ImportError as e:
        print("ERROR: Could not import backend:", e)
        print("Run from repo root: python scripts/item_views_ft05b.py")
        return 1

    # 1) Total views
    result = get_item_views_count(prefix=PREFIX)
    if result.get("error"):
        print("Error (total):", result["error"])
        return 1
    count = result.get("views_count", 0)
    prefix_used = result.get("item_id_prefix", PREFIX)
    print("1. Total views")
    print("   Item ID prefix:", prefix_used)
    print("   Views count:", f"{count:,}")
    print()

    # 2) Coming from Google
    result_google = _get_item_views_from_google(prefix_used)
    if result_google.get("error"):
        print("2. Views coming from Google")
        print("   Error:", result_google["error"])
        print()
    else:
        count_google = result_google.get("views_count", 0)
        print("2. Views coming from Google")
        print("   Item ID prefix:", prefix_used)
        print("   Views count:", f"{count_google:,}")
        print()

    print("Answer (total): The views count for item IDs starting with", prefix_used, "is", f"{count:,}.")
    if not result_google.get("error"):
        print("Answer (from Google): The views count for item IDs starting with", prefix_used, "coming from Google is", f"{result_google.get('views_count', 0):,}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
