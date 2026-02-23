"""Anomaly agent: read anomaly_flags and write anomaly insights to analytics_insights."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Optional

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.clients.bigquery import get_client, get_analytics_dataset, insert_insights


def run_anomaly_agent(
    client_ids: Optional[list[int]] = None,
    write: bool = True,
) -> list:
    """Load anomaly_flags for high-priority clients, create insights with insight_type=anomaly."""
    client = get_client()
    project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
    dataset = get_analytics_dataset()
    ids_filter = ""
    if client_ids:
        ids_filter = f" AND client_id IN ({','.join(map(str, client_ids))})"
    query = f"""
    SELECT client_id, campaign_id, date, is_anomaly, anomaly_score, revenue, predicted_revenue
    FROM `{project}.{dataset}.anomaly_flags`
    WHERE is_anomaly = TRUE {ids_filter}
      AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
    """
    df = client.query(query).to_dataframe()
    if df.empty:
        return []
    insights = []
    for _, row in df.iterrows():
        entity_id = f"{row['campaign_id']}_{row['date']}"
        period = str(row["date"])
        insight_id = hashlib.sha256(f"anomaly|campaign|{entity_id}|{period}".encode()).hexdigest()[:32]
        insights.append({
            "insight_id": insight_id,
            "client_id": int(row["client_id"]),
            "entity_type": "campaign",
            "entity_id": entity_id,
            "insight_type": "anomaly",
            "summary": f"Revenue anomaly for campaign {row['campaign_id']} on {row['date']}: actual {row.get('revenue')}, predicted {row.get('predicted_revenue')}.",
            "explanation": f"Anomaly score {row.get('anomaly_score', 0):.2f}. Review campaign performance.",
            "recommendation": "Review campaign and audience; consider pausing if sustained.",
            "expected_impact": {"metric": "revenue", "estimate": 0.0, "units": "currency"},
            "confidence": min(0.9, 0.5 + float(row.get("anomaly_score", 0) or 0) / 10),
            "evidence": [{"metric": "revenue", "value": float(row.get("revenue") or 0), "baseline": float(row.get("predicted_revenue") or 0), "period": "1d"}],
            "detected_by": ["anomaly_agent"],
            "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "applied_at": None,
            "history": None,
        })
    if write and insights:
        insert_insights(insights)
    return insights


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--clients", type=str, help="Comma-separated client IDs")
    args = p.parse_args()
    client_ids = [int(x) for x in args.clients.split(",")] if getattr(args, "clients", None) else None
    run_anomaly_agent(client_ids=client_ids, write=not args.no_write)
