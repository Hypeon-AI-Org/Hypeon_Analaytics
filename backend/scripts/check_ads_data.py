#!/usr/bin/env python3
"""
Check how data looks in Google Ads: raw AdGroupBasicStats table and ads_daily_staging.
Uses BQ_SOURCE_PROJECT, ADS_DATASET (raw, in EU), BQ_PROJECT, ANALYTICS_DATASET (staging in europe-north2), BQ_LOCATION_ADS.
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
ADS_DATASET = os.environ.get("ADS_DATASET", "146568")
BQ_LOCATION_ADS = os.environ.get("BQ_LOCATION_ADS", "EU")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "europe-north2")

# Same table name as in create_unified_table_ads_only.sql
ADS_RAW_TABLE = "ads_AdGroupBasicStats_4221201460"


def main():
    from google.cloud import bigquery

    # ---- 1) Raw Google Ads table (in EU) ----
    client_ads = bigquery.Client(project=BQ_SOURCE_PROJECT, location=BQ_LOCATION_ADS)

    q_raw = f"""
    SELECT
      COUNT(*) AS row_count,
      MIN(segments_date) AS min_date,
      MAX(segments_date) AS max_date,
      COUNT(DISTINCT customer_id) AS distinct_customers,
      SUM(COALESCE(metrics_cost_micros, 0)) / 1e6 AS total_spend,
      SUM(COALESCE(metrics_clicks, 0)) AS total_clicks,
      SUM(COALESCE(metrics_impressions, 0)) AS total_impressions,
      SUM(COALESCE(metrics_conversions, 0)) AS total_conversions,
      SUM(COALESCE(metrics_conversions_value, 0)) AS total_revenue
    FROM `{BQ_SOURCE_PROJECT}.{ADS_DATASET}.{ADS_RAW_TABLE}`
    WHERE segments_date IS NOT NULL
      AND customer_id IS NOT NULL
    """
    print("=== Raw Google Ads (AdGroupBasicStats, source in EU) ===")
    try:
        df = client_ads.query(q_raw).to_dataframe()
        if df.empty:
            print("No rows in raw Ads table.")
        else:
            print(df.to_string())
    except Exception as e:
        print(f"Error: {e}")
        return 1

    # ---- 2) Raw Ads: by customer_id (client_id) summary ----
    q_by_customer = f"""
    SELECT
      CAST(customer_id AS INT64) AS client_id,
      COUNT(*) AS row_count,
      MIN(segments_date) AS min_date,
      MAX(segments_date) AS max_date,
      SUM(COALESCE(metrics_cost_micros, 0)) / 1e6 AS spend,
      SUM(COALESCE(metrics_conversions_value, 0)) AS revenue
    FROM `{BQ_SOURCE_PROJECT}.{ADS_DATASET}.{ADS_RAW_TABLE}`
    WHERE segments_date IS NOT NULL
      AND customer_id IS NOT NULL
    GROUP BY customer_id
    ORDER BY spend DESC
    LIMIT 15
    """
    print("\n=== Raw Ads by customer_id (top 15 by spend) ===")
    try:
        df2 = client_ads.query(q_by_customer).to_dataframe()
        if df2.empty:
            print("No rows.")
        else:
            print(df2.to_string())
    except Exception as e:
        print(f"Error: {e}")

    # ---- 3) ads_daily_staging (pipeline output; in europe-north2 after copy) ----
    client_main = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION)
    q_staging = f"""
    SELECT
      COUNT(*) AS row_count,
      MIN(date) AS min_date,
      MAX(date) AS max_date,
      SUM(spend) AS total_spend,
      SUM(clicks) AS total_clicks,
      SUM(impressions) AS total_impressions,
      SUM(conversions) AS total_conversions,
      SUM(revenue) AS total_revenue,
      SUM(sessions) AS total_sessions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.ads_daily_staging`
    """
    print("\n=== ads_daily_staging (pipeline output in analytics) ===")
    try:
        df3 = client_main.query(q_staging).to_dataframe()
        if df3.empty:
            print("No rows.")
        else:
            print(df3.to_string())
    except Exception as e:
        print(f"Error (table may not exist yet): {e}")

    # ---- 4) Sample rows from ads_daily_staging ----
    q_sample = f"""
    SELECT client_id, date, channel, campaign_id, ad_group_id, device,
           spend, clicks, impressions, conversions, revenue, sessions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.ads_daily_staging`
    ORDER BY date DESC, spend DESC
    LIMIT 15
    """
    print("\n=== ads_daily_staging sample (last 15 rows by date, spend) ===")
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
