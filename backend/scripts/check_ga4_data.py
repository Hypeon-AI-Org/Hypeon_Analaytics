#!/usr/bin/env python3
"""
Check how data looks in GA4: raw events_* and marketing_performance_daily (channel=ga4).
Uses BQ_SOURCE_PROJECT, GA4_DATASET (raw), BQ_PROJECT, ANALYTICS_DATASET, BQ_LOCATION.
"""
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

BQ_PROJECT = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
BQ_SOURCE_PROJECT = os.environ.get("BQ_SOURCE_PROJECT") or BQ_PROJECT
ANALYTICS_DATASET = os.environ.get("ANALYTICS_DATASET", "analytics")
GA4_DATASET = os.environ.get("GA4_DATASET", "analytics_444259275")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "europe-north2")


def main():
    from google.cloud import bigquery

    # GA4 dataset lives in BQ_LOCATION (europe-north2)
    client = bigquery.Client(project=BQ_SOURCE_PROJECT, location=BQ_LOCATION)

    # ---- 1) Raw GA4 events_* summary ----
    q_raw = f"""
    SELECT
      COUNT(*) AS event_count,
      MIN(PARSE_DATE('%Y%m%d', event_date)) AS min_date,
      MAX(PARSE_DATE('%Y%m%d', event_date)) AS max_date,
      COUNTIF(event_name = 'purchase' OR event_name = 'conversion') AS conversion_events,
      COALESCE(SUM(COALESCE((SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value'), 0)), 0) AS sum_value_param,
      COALESCE(SUM(CAST((SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value') AS FLOAT64)), 0) AS sum_value_double
    FROM `{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*`
    WHERE event_date IS NOT NULL
    """
    # GA4 export: revenue is often in event_value_in_usd (top-level in some exports) or in event_params
    # Try standard GA4 export schema: event_value_in_usd exists in events table
    q_raw_v2 = f"""
    SELECT
      COUNT(*) AS event_count,
      MIN(PARSE_DATE('%Y%m%d', event_date)) AS min_date,
      MAX(PARSE_DATE('%Y%m%d', event_date)) AS max_date,
      COUNTIF(event_name = 'purchase' OR event_name = 'conversion') AS conversion_events,
      COALESCE(SUM(COALESCE(event_value_in_usd, 0)), 0) AS total_revenue_usd
    FROM `{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*`
    WHERE event_date IS NOT NULL
    """
    print("=== Raw GA4 events_* (source dataset) ===")
    try:
        df = client.query(q_raw_v2).to_dataframe()
        if df.empty:
            print("No rows in GA4 events_*")
        else:
            print(df.to_string())
    except Exception as e:
        # Fallback if event_value_in_usd doesn't exist
        try:
            df = client.query(q_raw).to_dataframe()
            print(df.to_string())
        except Exception as e2:
            print(f"Error: {e2}")
            return 1

    # ---- 2) Event name distribution (sample) ----
    q_events = f"""
    SELECT event_name, COUNT(*) AS cnt
    FROM `{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*`
    WHERE event_date IS NOT NULL
    GROUP BY event_name
    ORDER BY cnt DESC
    LIMIT 15
    """
    print("\n=== Event names (top 15) ===")
    try:
        df2 = client.query(q_events).to_dataframe()
        print(df2.to_string())
    except Exception as e:
        print(f"Error: {e}")

    # ---- 3) marketing_performance_daily (GA4 channel only) ----
    client_main = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION)
    q_staging = f"""
    SELECT
      COUNT(*) AS row_count,
      MIN(date) AS min_date,
      MAX(date) AS max_date,
      SUM(spend) AS total_spend,
      SUM(revenue) AS total_revenue,
      SUM(conversions) AS total_conversions,
      SUM(sessions) AS total_sessions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily`
    WHERE channel = 'ga4'
    """
    print("\n=== marketing_performance_daily (channel=ga4) ===")
    try:
        df3 = client_main.query(q_staging).to_dataframe()
        print(df3.to_string())
    except Exception as e:
        print(f"Error (table may not exist yet): {e}")

    # ---- 4) Sample rows (GA4 from unified table) ----
    q_sample = f"""
    SELECT date, channel, device, spend, revenue, conversions, sessions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily`
    WHERE channel = 'ga4'
    ORDER BY date DESC
    LIMIT 10
    """
    print("\n=== marketing_performance_daily sample (ga4, last 10 rows) ===")
    try:
        df4 = client_main.query(q_sample).to_dataframe()
        if df4.empty:
            print("No rows.")
        else:
            print(df4.to_string())
    except Exception as e:
        print(f"Error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
