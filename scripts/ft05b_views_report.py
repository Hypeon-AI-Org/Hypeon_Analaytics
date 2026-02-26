#!/usr/bin/env python3
"""
Views count report for Item IDs starting with FT05B.

Answers:
  1. Total views count of Item Id starting with FT05B
  2. Views count of Item Id starting with FT05B coming from Google
  3. Views count of Item Id starting with FT05B coming from Facebook

Uses GA4 raw events in BigQuery (events_*). Loads BQ_PROJECT, BQ_SOURCE_PROJECT,
GA4_DATASET, BQ_LOCATION from .env. Run from repo root:
  python scripts/ft05b_views_report.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

BQ_SOURCE_PROJECT = os.environ.get("BQ_SOURCE_PROJECT") or os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
GA4_DATASET = os.environ.get("GA4_DATASET", "analytics_444259275")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "europe-north2")

# GA4 event that represents a product/item view
VIEW_ITEM_EVENTS = ("view_item", "view_item_list")


def run_query(client, query: str, description: str):
    """Run a BigQuery query and return (success, result_message)."""
    try:
        job = client.query(query)
        rows = list(job.result())
        if not rows:
            return True, "0"
        # First column of first row is the count
        count = rows[0][0] if rows else 0
        return True, str(count)
    except Exception as e:
        return False, str(e)


def main():
    from google.cloud import bigquery

    client = bigquery.Client(project=BQ_SOURCE_PROJECT, location=BQ_LOCATION)
    table_ref = f"`{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*`"

    # Base: events that have at least one item with item_id starting with FT05B.
    # We count one "view" per (event, item) pair so multiple items in one event are counted.
    base_from = f"""
    FROM {table_ref},
    UNNEST(COALESCE(items, [])) AS it
    WHERE event_date IS NOT NULL
      AND event_name IN {VIEW_ITEM_EVENTS}
      AND STARTS_WITH(COALESCE(it.item_id, ''), 'FT05B')
    """

    # 1) Total views count for Item Id starting with FT05B
    q1 = f"""
    SELECT COUNT(*) AS views_count
    {base_from}
    """
    ok1, msg1 = run_query(client, q1, "Total FT05B views")
    print("=" * 60)
    print("1. Views Count of Item Id starting with FT05B")
    print("=" * 60)
    if ok1:
        print(f"   Views count: {msg1}")
    else:
        print(f"   Error: {msg1}")
    print()

    # 2) Same but coming from Google (event-level or session-level source)
    # GA4: traffic_source.source or session_traffic_source_last_click.manual_campaign.source
    q2 = f"""
    SELECT COUNT(*) AS views_count
    {base_from}
      AND (
        LOWER(COALESCE(traffic_source.source, '')) LIKE '%google%'
        OR LOWER(COALESCE(
          (SELECT source FROM UNNEST([session_traffic_source_last_click.manual_campaign])),
          (SELECT source FROM UNNEST([session_traffic_source_last_click.cross_channel_campaign])),
          ''
        )) LIKE '%google%'
      )
    """
    # Simpler: use scalar subquery only when needed; GA4 schema has traffic_source at event level
    q2_simple = f"""
    SELECT COUNT(*) AS views_count
    {base_from}
      AND (
        LOWER(COALESCE(traffic_source.source, '')) LIKE '%google%'
        OR (session_traffic_source_last_click.manual_campaign IS NOT NULL
            AND LOWER(COALESCE(session_traffic_source_last_click.manual_campaign.source, '')) LIKE '%google%')
        OR (session_traffic_source_last_click.cross_channel_campaign IS NOT NULL
            AND LOWER(COALESCE(session_traffic_source_last_click.cross_channel_campaign.source, '')) LIKE '%google%')
      )
    """
    ok2, msg2 = run_query(client, q2_simple, "FT05B views from Google")
    print("=" * 60)
    print("2. Views Count of Item Id starting with FT05B coming From Google")
    print("=" * 60)
    if ok2:
        print(f"   Views count: {msg2}")
    else:
        print(f"   Error: {msg2}")
    print()

    # 3) Same but coming from Facebook
    q3_simple = f"""
    SELECT COUNT(*) AS views_count
    {base_from}
      AND (
        LOWER(COALESCE(traffic_source.source, '')) IN ('facebook', 'fb')
        OR LOWER(COALESCE(traffic_source.source, '')) LIKE '%facebook%'
        OR (session_traffic_source_last_click.manual_campaign IS NOT NULL
            AND LOWER(COALESCE(session_traffic_source_last_click.manual_campaign.source, '')) LIKE '%facebook%')
        OR (session_traffic_source_last_click.manual_campaign IS NOT NULL
            AND LOWER(COALESCE(session_traffic_source_last_click.manual_campaign.source, '')) = 'fb')
        OR (session_traffic_source_last_click.cross_channel_campaign IS NOT NULL
            AND LOWER(COALESCE(session_traffic_source_last_click.cross_channel_campaign.source, '')) LIKE '%facebook%')
      )
    """
    ok3, msg3 = run_query(client, q3_simple, "FT05B views from Facebook")
    print("=" * 60)
    print("3. Views Count of Item Id starting with FT05B coming From Facebook")
    print("=" * 60)
    if ok3:
        print(f"   Views count: {msg3}")
    else:
        print(f"   Error: {msg3}")
    print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Total (FT05B*):     {msg1 if ok1 else 'N/A'}")
    print(f"  From Google:        {msg2 if ok2 else 'N/A'}")
    print(f"  From Facebook:      {msg3 if ok3 else 'N/A'}")

    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    sys.exit(main())
