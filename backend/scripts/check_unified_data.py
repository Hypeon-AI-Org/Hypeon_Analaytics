#!/usr/bin/env python3
"""Quick check: marketing_performance_daily for client_id=1 (date range and sample aggregates)."""
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

from backend.app.config import get_bq_project, get_analytics_dataset


def main():
    from google.cloud import bigquery
    project = get_bq_project()
    dataset = get_analytics_dataset()
    client = bigquery.Client(project=project)

    # 1) Summary for client_id=1 in last 28 days
    q1 = f"""
    SELECT
      client_id,
      COUNT(*) AS row_count,
      SUM(spend) AS total_spend,
      SUM(revenue) AS total_revenue,
      MIN(date) AS min_date,
      MAX(date) AS max_date
    FROM `{project}.{dataset}.marketing_performance_daily`
    WHERE client_id = 1
      AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 28 DAY)
      AND date <= CURRENT_DATE()
    GROUP BY client_id
    """
    print("=== Summary (client_id=1, last 28 days) ===")
    try:
        df = client.query(q1).to_dataframe()
        if df.empty:
            print("No rows for client_id=1 in last 28 days.")
        else:
            print(df.to_string())
    except Exception as e:
        print(f"Error: {e}")
        return 1

    # 2) Sample aggregates by entity (what rules see)
    q2 = f"""
    SELECT
      client_id, channel, campaign_id, ad_group_id, device,
      SUM(spend) AS spend,
      SUM(revenue) AS revenue,
      SUM(sessions) AS sessions,
      SAFE_DIVIDE(SUM(revenue), NULLIF(SUM(spend), 0)) AS roas
    FROM `{project}.{dataset}.marketing_performance_daily`
    WHERE client_id = 1
      AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 28 DAY)
      AND date <= CURRENT_DATE()
    GROUP BY client_id, channel, campaign_id, ad_group_id, device
    ORDER BY spend DESC
    LIMIT 20
    """
    print("\n=== Sample aggregates (top 20 by spend) ===")
    try:
        df2 = client.query(q2).to_dataframe()
        if df2.empty:
            print("No aggregated rows.")
        else:
            print(df2.to_string())
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
