"""BigQuery client for HypeOn Analytics V1. Enterprise: organization_id, workspace_id, scoped queries."""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from typing import Any, Optional

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


def _project() -> str:
    return os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")


def load_marketing_performance(
    client_id: int,
    as_of_date: date,
    days: int = 28,
    organization_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    since_date: Optional[date] = None,
) -> pd.DataFrame:
    """Load marketing_performance_daily for client. If since_date set, only rows with date > since_date (incremental)."""
    client = get_client()
    dataset = get_analytics_dataset()
    project = _project()
    if since_date:
        start = since_date
        end = as_of_date
    else:
        start = as_of_date - timedelta(days=days)
        end = as_of_date
    query = f"""
    SELECT *
    FROM `{project}.{dataset}.marketing_performance_daily`
    WHERE client_id = {client_id}
      AND date >= '{start.isoformat()}'
      AND date <= '{end.isoformat()}'
    """
    return client.query(query).to_dataframe()


def insert_insights(rows: list[dict[str, Any]]) -> None:
    """Insert insight rows into analytics_insights. Caller ensures idempotency (insight_hash)."""
    if not rows:
        return
    client = get_client()
    table_id = f"{_project()}.{get_analytics_dataset()}.analytics_insights"
    errors = client.insert_rows_json(table_id, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")


def insert_decision_history(
    organization_id: str,
    client_id: int,
    insight_id: str,
    recommended_action: str,
    status: str,
    applied_by: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> None:
    from datetime import datetime, timezone
    client = get_client()
    now = datetime.now(timezone.utc)
    row = {
        "history_id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "client_id": client_id,
        "workspace_id": workspace_id,
        "insight_id": insight_id,
        "recommended_action": recommended_action,
        "status": status,
        "applied_by": applied_by,
        "applied_at": now.isoformat(),
        "outcome_metrics_after_7d": None,
        "outcome_metrics_after_30d": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    table_id = f"{_project()}.{get_analytics_dataset()}.decision_history"
    errors = client.insert_rows_json(table_id, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")


def get_decision_history(
    organization_id: str,
    client_id: Optional[int] = None,
    insight_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()
    def esc(s: str) -> str:
        return (s or "").replace("'", "''")
    where = [f"organization_id = '{esc(organization_id)}'"]
    if client_id is not None:
        where.append(f"client_id = {client_id}")
    if insight_id:
        where.append(f"insight_id = '{esc(insight_id)}'")
    if status:
        where.append(f"status = '{esc(status)}'")
    q = f"""
    SELECT * FROM `{project}.{dataset}.decision_history`
    WHERE {' AND '.join(where)}
    ORDER BY created_at DESC
    LIMIT {limit}
    """
    df = client.query(q).to_dataframe()
    if df.empty:
        return []
    return [dict(row) for _, row in df.iterrows()]


def list_insights(
    organization_id: str,
    client_id: Optional[int] = None,
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List insights scoped by organization_id; no cross-tenant leakage."""
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()

    def esc(s: str) -> str:
        return (s or "").replace("'", "''")
    where = [f"organization_id = '{esc(organization_id)}'"]
    if client_id is not None:
        where.append(f"client_id = {client_id}")
    if workspace_id:
        where.append(f"workspace_id = '{esc(workspace_id)}'")
    if status:
        where.append(f"status = '{esc(status)}'")
    if not where:
        where.append("1=1")
    q = f"""
    SELECT * FROM `{project}.{dataset}.analytics_insights`
    WHERE {' AND '.join(where)}
    ORDER BY created_at DESC
    LIMIT {limit} OFFSET {offset}
    """
    df = client.query(q).to_dataframe()
    if df.empty:
        return []
    return [dict(row) for _, row in df.iterrows()]


def get_insight_by_id(insight_id: str, organization_id: Optional[str] = None) -> Optional[dict]:
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()

    def esc(s: str) -> str:
        return (s or "").replace("'", "''")
    where = [f"insight_id = '{esc(insight_id)}'"]
    if organization_id:
        where.append(f"organization_id = '{esc(organization_id)}'")
    q = f"SELECT * FROM `{project}.{dataset}.analytics_insights` WHERE {' AND '.join(where)} LIMIT 1"
    try:
        df = client.query(q).to_dataframe()
    except Exception:
        q_fallback = f"SELECT * FROM `{project}.{dataset}.analytics_insights` WHERE insight_id = '{esc(insight_id)}' LIMIT 1"
        df = client.query(q_fallback).to_dataframe()
    if df.empty:
        return None
    return dict(df.iloc[0])


def get_supporting_metrics_snapshot(organization_id: str, client_id: int, insight_id: str) -> Optional[dict]:
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()
    q = f"""
    SELECT metrics_json FROM `{project}.{dataset}.supporting_metrics_snapshot`
    WHERE organization_id = '{organization_id.replace("'", "''")}' AND client_id = {client_id} AND insight_id = '{insight_id.replace("'", "''")}'
    ORDER BY created_at DESC LIMIT 1
    """
    df = client.query(q).to_dataframe()
    if df.empty:
        return None
    import json
    raw = df.iloc[0].get("metrics_json")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
