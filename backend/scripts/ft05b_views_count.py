#!/usr/bin/env python3
"""
Views count of Item Id starting with FT05B (or a custom prefix).

Queries GA4 raw events_* in BigQuery: counts view_item / view_item_list events
where at least one item has item_id starting with the given prefix.

Uses .env: BQ_PROJECT, BQ_SOURCE_PROJECT, GA4_DATASET, BQ_LOCATION.

Run from repo root:
  python backend/scripts/ft05b_views_count.py
  python backend/scripts/ft05b_views_count.py --prefix FT05B
  python backend/scripts/ft05b_views_count.py --prefix FT06
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

BQ_SOURCE_PROJECT = os.environ.get("BQ_SOURCE_PROJECT") or os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
GA4_DATASET = os.environ.get("GA4_DATASET", "analytics_444259275")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "europe-north2")

VIEW_ITEM_EVENTS = ("view_item", "view_item_list")


def main():
    parser = argparse.ArgumentParser(description="Views count of Item Id starting with a given prefix (default FT05B).")
    parser.add_argument("--prefix", default="FT05B", help="Item ID prefix (e.g. FT05B)")
    parser.add_argument("--json", action="store_true", help="Output only the number as JSON: {\"views_count\": N}")
    args = parser.parse_args()

    prefix = (args.prefix or "FT05B").strip()
    if not prefix:
        prefix = "FT05B"

    from google.cloud import bigquery

    client = bigquery.Client(project=BQ_SOURCE_PROJECT, location=BQ_LOCATION)
    table_ref = f"`{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*`"

    query = f"""
    SELECT COUNT(*) AS views_count
    FROM {table_ref},
    UNNEST(COALESCE(items, [])) AS it
    WHERE event_date IS NOT NULL
      AND event_name IN {VIEW_ITEM_EVENTS}
      AND STARTS_WITH(COALESCE(it.item_id, ''), @prefix)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("prefix", "STRING", prefix),
        ]
    )

    try:
        job = client.query(query, job_config=job_config)
        rows = list(job.result())
        count = int(rows[0][0]) if rows else 0
    except Exception as e:
        if args.json:
            print(f'{{"error": "{str(e)[:200].replace(chr(34), chr(39))}", "views_count": null}}')
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(f'{{"views_count": {count}, "item_id_prefix": "{prefix}"}}')
    else:
        print("Views count of Item Id starting with", prefix)
        print("=" * 50)
        print(count)

    return 0


if __name__ == "__main__":
    sys.exit(main())
