#!/usr/bin/env python3
"""
Analytics data report: GA4, Google Ads, hypeon-ai-prod analytics dataset.
Run from repo root: python backend/scripts/analytics_data_report.py
Output: analytics_data_report.md (and stdout).
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

BQ_PROJECT = os.environ.get("BQ_PROJECT", "hypeon-ai-prod")
BQ_SOURCE_PROJECT = os.environ.get("BQ_SOURCE_PROJECT") or BQ_PROJECT
ANALYTICS_DATASET = os.environ.get("ANALYTICS_DATASET", "analytics")
GA4_DATASET = os.environ.get("GA4_DATASET", "analytics_444259275")
ADS_DATASET = os.environ.get("ADS_DATASET", "146568")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "europe-north2")
BQ_LOCATION_ADS = os.environ.get("BQ_LOCATION_ADS", "EU")
ADS_RAW_TABLE = "ads_AdGroupBasicStats_4221201460"


def run_query(client, query, name):
    try:
        df = client.query(query).to_dataframe()
        return None if df.empty else df
    except Exception as e:
        return str(e)


def main():
    from google.cloud import bigquery

    lines = []
    def log(s=""):
        print(s)
        lines.append(s)

    log("# Analytics Data Report")
    log(f"Generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}")
    log()
    log("## Configuration")
    log(f"- **BQ_PROJECT (app DB):** `{BQ_PROJECT}` (hypeon-ai-prod)")
    log(f"- **BQ_SOURCE_PROJECT (raw data):** `{BQ_SOURCE_PROJECT}`")
    log(f"- **ANALYTICS_DATASET:** `{ANALYTICS_DATASET}`")
    log(f"- **GA4_DATASET (raw):** `{GA4_DATASET}`")
    log(f"- **ADS_DATASET (raw):** `{ADS_DATASET}`")
    log()

    client_source_ga4 = bigquery.Client(project=BQ_SOURCE_PROJECT, location=BQ_LOCATION)
    client_source_ads = bigquery.Client(project=BQ_SOURCE_PROJECT, location=BQ_LOCATION_ADS)
    client_app = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION)

    # ----- 1) hypeon-ai-prod.analytics: what tables exist and row counts -----
    log("## 1. hypeon-ai-prod (BQ_PROJECT) - Analytics dataset")
    try:
        tables = list(client_app.list_tables(f"{BQ_PROJECT}.{ANALYTICS_DATASET}"))
        if not tables:
            log("No tables found in dataset.")
        else:
            for t in tables:
                tid = t.table_id
                q = f"SELECT COUNT(*) AS n FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.{tid}`"
                r = run_query(client_app, q, tid)
                if isinstance(r, str):
                    log(f"- **{tid}**: error - {r}")
                else:
                    n = int(r["n"].iloc[0]) if r is not None else 0
                    log(f"- **{tid}**: {n:,} rows")
    except Exception as e:
        log(f"Error listing tables: {e}")
    log()

    # ----- 2) Raw GA4 (source project) -----
    log("## 2. Google Analytics (GA4) - Raw events (source project)")
    q_ga4_raw = f"""
    SELECT
      COUNT(*) AS event_count,
      MIN(PARSE_DATE('%Y%m%d', event_date)) AS min_date,
      MAX(PARSE_DATE('%Y%m%d', event_date)) AS max_date,
      COUNTIF(event_name = 'purchase' OR event_name = 'conversion') AS conversion_events,
      COALESCE(SUM(COALESCE(event_value_in_usd, 0)), 0) AS total_revenue_usd
    FROM `{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*`
    WHERE event_date IS NOT NULL
    """
    r = run_query(client_source_ga4, q_ga4_raw, "ga4_raw")
    if isinstance(r, str):
        log(f"Error: {r}")
    elif r is not None:
        log(r.to_string())
        event_count = int(r["event_count"].iloc[0])
        if event_count == 0:
            log("**No GA4 events in raw dataset.**")
    else:
        log("No rows.")
    log()

    # ----- 3) GA4 daily staging (hypeon-ai-prod) -----
    log("## 3. GA4 daily staging (hypeon-ai-prod.analytics.ga4_daily_staging)")
    q_ga4_staging = f"""
    SELECT
      COUNT(*) AS row_count,
      MIN(date) AS min_date,
      MAX(date) AS max_date,
      SUM(spend) AS total_spend,
      SUM(revenue) AS total_revenue,
      SUM(conversions) AS total_conversions,
      SUM(sessions) AS total_sessions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.ga4_daily_staging`
    """
    r = run_query(client_app, q_ga4_staging, "ga4_staging")
    if isinstance(r, str):
        log(f"Error (table may not exist): {r}")
    elif r is not None:
        log(r.to_string())
        rc = int(r["row_count"].iloc[0])
        if rc == 0:
            log("**Table exists but has no rows.**")
    else:
        log("No rows.")
    log()

    # ----- 4) Raw Google Ads (source project, EU) -----
    log("## 4. Google Ads - Raw (source project, EU)")
    q_ads_raw = f"""
    SELECT
      COUNT(*) AS row_count,
      MIN(segments_date) AS min_date,
      MAX(segments_date) AS max_date,
      SUM(COALESCE(metrics_cost_micros, 0)) / 1e6 AS total_spend,
      SUM(COALESCE(metrics_conversions_value, 0)) AS total_revenue,
      SUM(COALESCE(metrics_clicks, 0)) AS total_clicks,
      SUM(COALESCE(metrics_impressions, 0)) AS total_impressions
    FROM `{BQ_SOURCE_PROJECT}.{ADS_DATASET}.{ADS_RAW_TABLE}`
    WHERE segments_date IS NOT NULL AND customer_id IS NOT NULL
    """
    r = run_query(client_source_ads, q_ads_raw, "ads_raw")
    if isinstance(r, str):
        log(f"Error: {r}")
    elif r is not None:
        log(r.to_string())
        rc = int(r["row_count"].iloc[0])
        if rc == 0:
            log("**No rows in raw Ads table.**")
    else:
        log("No rows.")
    log()

    # ----- 5) Ads daily staging (hypeon-ai-prod) -----
    log("## 5. Google Ads daily staging (hypeon-ai-prod.analytics.ads_daily_staging)")
    q_ads_staging = f"""
    SELECT
      COUNT(*) AS row_count,
      MIN(date) AS min_date,
      MAX(date) AS max_date,
      SUM(spend) AS total_spend,
      SUM(revenue) AS total_revenue,
      SUM(clicks) AS total_clicks,
      SUM(impressions) AS total_impressions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.ads_daily_staging`
    """
    r = run_query(client_app, q_ads_staging, "ads_staging")
    if isinstance(r, str):
        log(f"Error (table may not exist): {r}")
    elif r is not None:
        log(r.to_string())
        rc = int(r["row_count"].iloc[0])
        if rc == 0:
            log("**Table exists but has no rows.**")
    else:
        log("No rows.")
    log()

    # ----- 6) marketing_performance_daily (hypeon-ai-prod) -----
    log("## 6. Unified table (hypeon-ai-prod.analytics.marketing_performance_daily)")
    q_union = f"""
    SELECT
      COUNT(*) AS row_count,
      COUNT(DISTINCT client_id) AS clients,
      MIN(date) AS min_date,
      MAX(date) AS max_date,
      SUM(spend) AS total_spend,
      SUM(revenue) AS total_revenue,
      SUM(sessions) AS total_sessions,
      SUM(conversions) AS total_conversions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily`
    """
    r = run_query(client_app, q_union, "marketing_performance_daily")
    if isinstance(r, str):
        log(f"Error (table may not exist): {r}")
    elif r is not None:
        log(r.to_string())
        rc = int(r["row_count"].iloc[0])
        if rc == 0:
            log("**Unified table is empty - dashboard/Copilot will have no data.**")
    else:
        log("No rows.")
    log()

    # ----- 7) Sample rows: ga4_daily_staging -----
    log("## 7. Sample: ga4_daily_staging (last 5 rows)")
    q_sample_ga4 = f"""
    SELECT date, channel, device, spend, revenue, conversions, sessions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.ga4_daily_staging`
    ORDER BY date DESC
    LIMIT 5
    """
    r = run_query(client_app, q_sample_ga4, "sample_ga4")
    if isinstance(r, str):
        log(f"Error: {r}")
    elif r is not None and not r.empty:
        log(r.to_string())
    else:
        log("No rows.")
    log()

    # ----- 8) Sample rows: ads_daily_staging -----
    log("## 8. Sample: ads_daily_staging (last 5 rows)")
    q_sample_ads = f"""
    SELECT client_id, date, channel, spend, revenue, clicks, conversions
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.ads_daily_staging`
    ORDER BY date DESC
    LIMIT 5
    """
    r = run_query(client_app, q_sample_ads, "sample_ads")
    if isinstance(r, str):
        log(f"Error: {r}")
    elif r is not None and not r.empty:
        log(r.to_string())
    else:
        log("No rows.")
    log()

    # ----- 9) Sample: marketing_performance_daily -----
    log("## 9. Sample: marketing_performance_daily (last 5 rows)")
    q_sample_mp = f"""
    SELECT client_id, date, channel, spend, revenue, sessions, conversions, roas
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily`
    ORDER BY date DESC
    LIMIT 5
    """
    r = run_query(client_app, q_sample_mp, "sample_mp")
    if isinstance(r, str):
        log(f"Error: {r}")
    elif r is not None and not r.empty:
        log(r.to_string())
    else:
        log("No rows.")
    log()

    # ----- 10) analytics_insights (hypeon-ai-prod) -----
    log("## 10. Decision store (analytics_insights)")
    q_insights = f"""
    SELECT COUNT(*) AS n, status
    FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights`
    GROUP BY status
    """
    r = run_query(client_app, q_insights, "insights")
    if isinstance(r, str):
        log(f"Error (table may not exist): {r}")
    elif r is not None and not r.empty:
        log(r.to_string())
    else:
        log("No rows or table missing.")
    log()

    # ----- Verdict -----
    log("---")
    log("## Verdict: Can we use the current analytics data?")
    log()
    log("Review the sections above. In general:")
    log("- **If raw GA4 events_* has 0 or very few events:** GA4 pipeline has little to work with; consider enabling GA4 export to BigQuery and ensuring the property receives traffic.")
    log("- **If raw Google Ads table has 0 rows:** Ads export to BigQuery may not be set up or linked; configure Google Ads to BigQuery export.")
    log("- **If ga4_daily_staging or ads_daily_staging are empty:** Run the unified pipeline (run_unified_table.py) after raw data exists; staging is populated by the SQL jobs.")
    log("- **If marketing_performance_daily is empty:** Run the union step (run_unified_table.py) so staging tables are combined; dashboard and Copilot depend on this table.")
    log("- **hypeon-ai-prod.analytics** holds the application tables; all staging and unified tables should live here when the pipeline runs against BQ_PROJECT=hypeon-ai-prod.")
    log()

    out_path = ROOT / "analytics_data_report.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
