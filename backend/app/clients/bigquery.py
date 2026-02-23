"""BigQuery client for HypeOn Analytics V1."""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import pandas as pd

_client: Any = None


def get_client():
    global _client
    if _client is None:
        from google.cloud import bigquery
        project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
        _client = bigquery.Client(project=project)
    return _client


def get_analytics_dataset() -> str:
    return os.environ.get("ANALYTICS_DATASET", "analytics")


def load_marketing_performance(
    client_id: int,
    as_of_date: date,
    days: int = 28,
) -> pd.DataFrame:
    """Load last `days` of marketing_performance_daily for client. Returns a DataFrame."""
    client = get_client()
    dataset = get_analytics_dataset()
    project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
    start = as_of_date - timedelta(days=days)
    query = f"""
    SELECT *
    FROM `{project}.{dataset}.marketing_performance_daily`
    WHERE client_id = {client_id}
      AND date >= '{start.isoformat()}'
      AND date <= '{as_of_date.isoformat()}'
    """
    return client.query(query).to_dataframe()


def insert_insights(rows: list[dict[str, Any]]) -> None:
    """Insert insight rows into analytics_insights. Caller ensures idempotency (e.g. MERGE by insight_id)."""
    if not rows:
        return
    client = get_client()
    project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
    dataset = get_analytics_dataset()
    table_id = f"{project}.{dataset}.analytics_insights"
    errors = client.insert_rows_json(table_id, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")
