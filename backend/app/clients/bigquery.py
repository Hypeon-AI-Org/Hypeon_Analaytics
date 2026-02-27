"""BigQuery client for HypeOn Analytics V1. Enterprise: organization_id, workspace_id, scoped queries."""
from __future__ import annotations

import math
import os
import uuid
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd


def _is_table_not_found(exc: BaseException) -> bool:
    """True if the exception indicates a missing table (404 / not found)."""
    msg = (str(exc) or "").lower()
    return "not found" in msg or "404" in msg or "notfound" in msg

_client: Any = None


def get_client():
    global _client
    if _client is None:
        from google.cloud import bigquery
        project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
        location = os.environ.get("BQ_LOCATION")
        _client = bigquery.Client(project=project, location=location) if location else bigquery.Client(project=project)
    return _client


def get_analytics_dataset() -> str:
    return os.environ.get("ANALYTICS_DATASET", "analytics")


def get_ads_dataset() -> str:
    """Dataset for Ads raw/staging (from .env ADS_DATASET, e.g. 146568). Used by Copilot run_sql."""
    return os.environ.get("ADS_DATASET", "146568")


def get_ga4_dataset() -> str:
    """Dataset for GA4 raw/staging (from .env GA4_DATASET, e.g. analytics_444259275). Used by Copilot run_sql."""
    return os.environ.get("GA4_DATASET", "analytics_444259275")


def _project() -> str:
    return os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")


def _source_project() -> str:
    """Project where GA4/Ads raw data lives (e.g. events_*). Used for item views count."""
    return os.environ.get("BQ_SOURCE_PROJECT") or _project()


# Copilot run_sql: allow any table in ADS_DATASET and GA4_DATASET only (raw datasets from .env)
def _copilot_allowed_datasets() -> frozenset[str]:
    """Return set of dataset IDs (lower) allowed for run_sql. Any table in these datasets is allowed."""
    ads_ds = get_ads_dataset().strip().lower()
    ga4_ds = get_ga4_dataset().strip().lower()
    return frozenset({ads_ds, ga4_ds})


def run_readonly_query(
    sql: str,
    client_id: int,
    organization_id: str,
    max_rows: int = 500,
    timeout_sec: float = 15.0,
) -> dict:
    """
    Run a read-only BigQuery query for Copilot. Validates SELECT only and allowed tables.
    Returns {"rows": [...], "error": None} or {"rows": [], "error": "message"}.
    """
    import re
    from google.cloud import bigquery

    sql = (sql or "").strip()
    if not sql:
        return {"rows": [], "error": "Empty query."}

    # Single statement only: no semicolon (except trailing)
    sql_normalized = sql.rstrip(";").strip()
    if ";" in sql_normalized:
        return {"rows": [], "error": "Only a single SELECT statement is allowed."}

    # Must be SELECT only (allow WITH ... SELECT)
    upper = sql_normalized.upper()
    if not upper.startswith("SELECT") and not upper.startswith("WITH"):
        return {"rows": [], "error": "Only SELECT (or WITH ... SELECT) queries are allowed."}
    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "GRANT", "REVOKE"):
        if verb in upper:
            return {"rows": [], "error": f"Only read-only SELECT is allowed (no {verb})."}

    project = _project().lower()
    source_project = _source_project().lower()
    allowed_datasets = _copilot_allowed_datasets()
    # Match backtick-quoted identifiers: `project.dataset.table`
    pattern = r"`([^`]+)`"
    for match in re.finditer(pattern, sql):
        ref = match.group(1).strip().lower()
        parts = ref.split(".")
        if len(parts) != 3:
            continue
        ref_project, ref_dataset, table_part = parts
        if ref_dataset not in allowed_datasets:
            return {"rows": [], "error": f"Dataset not allowed for Copilot: {ref_dataset}. Only ADS_DATASET and GA4_DATASET are allowed (see .env)."}
        if ref_project not in (project, source_project):
            return {"rows": [], "error": f"Only tables in project {_project()} or {_source_project()} are allowed."}

    # Enforce LIMIT if not present (BigQuery allows no LIMIT but we want to cap rows)
    if "LIMIT" not in upper:
        sql_normalized = f"{sql_normalized} LIMIT {max_rows}"

    client = get_client()
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=100 * 1024 * 1024,  # 100 MB cap
    )
    try:
        query_job = client.query(sql_normalized, job_config=job_config)
        # Wait with timeout; then fetch up to max_rows
        iterator = query_job.result(max_results=max_rows, timeout=timeout_sec)
        rows = []
        for row in iterator:
            rows.append(dict(row.items()))
        return {"rows": rows, "error": None}
    except Exception as e:
        return {"rows": [], "error": str(e)[:300]}


# GA4 events that represent a product/item view (for get_item_views_count)
_VIEW_ITEM_EVENTS = ("view_item", "view_item_list")


def get_item_views_count(prefix: str = "FT05B") -> dict:
    """
    Return views count for item_id starting with prefix from GA4 raw events_*.
    Returns {"views_count": int, "item_id_prefix": str} or {"error": str}.
    Uses BQ_SOURCE_PROJECT, GA4_DATASET, BQ_LOCATION from env.
    """
    from google.cloud import bigquery

    prefix = (prefix or "FT05B").strip() or "FT05B"
    project = _source_project()
    dataset = get_ga4_dataset()
    location = os.environ.get("BQ_LOCATION", "europe-north2")
    table_ref = f"`{project}.{dataset}.events_*`"
    query = f"""
    SELECT COUNT(*) AS views_count
    FROM {table_ref},
    UNNEST(COALESCE(items, [])) AS it
    WHERE event_date IS NOT NULL
      AND event_name IN {_VIEW_ITEM_EVENTS}
      AND STARTS_WITH(COALESCE(it.item_id, ''), @prefix)
    """
    # events_* scan can exceed 100 MB; allow 200 MB for this specific query
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("prefix", "STRING", prefix),
        ],
        maximum_bytes_billed=200 * 1024 * 1024,
    )
    try:
        client = bigquery.Client(project=project, location=location)
        job = client.query(query, job_config=job_config)
        rows = list(job.result(timeout=30))
        count = int(rows[0][0]) if rows else 0
        return {"views_count": count, "item_id_prefix": prefix}
    except Exception as e:
        return {"error": str(e)[:300], "views_count": None, "item_id_prefix": prefix}


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


def load_ads_staging(
    client_id: int,
    start_date: date,
    end_date: date,
    organization_id: Optional[str] = None,
) -> pd.DataFrame:
    """Load raw Google Ads data from ads_daily_staging (dataset from ADS_DATASET)."""
    client = get_client()
    dataset = get_ads_dataset()
    project = _project()
    query = f"""
    SELECT client_id, date, campaign_id, ad_group_id, device,
           spend, clicks, impressions, conversions, revenue
    FROM `{project}.{dataset}.ads_daily_staging`
    WHERE client_id = {client_id}
      AND date >= '{start_date.isoformat()}'
      AND date <= '{end_date.isoformat()}'
    ORDER BY date
    """
    return client.query(query).to_dataframe()


def load_ga4_staging(
    client_id: int,
    start_date: date,
    end_date: date,
    organization_id: Optional[str] = None,
) -> pd.DataFrame:
    """Load raw GA4 data from ga4_daily_staging (dataset from GA4_DATASET)."""
    client = get_client()
    dataset = get_ga4_dataset()
    project = _project()
    query = f"""
    SELECT client_id, date, device,
           sessions, conversions, revenue
    FROM `{project}.{dataset}.ga4_daily_staging`
    WHERE client_id = {client_id}
      AND date >= '{start_date.isoformat()}'
      AND date <= '{end_date.isoformat()}'
    ORDER BY date
    """
    return client.query(query).to_dataframe()


def _sanitize_for_json(obj: Any) -> Any:
    """Replace NaN/Inf and non-JSON-serializable values so insert_rows_json succeeds."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(x) for x in obj]
    if isinstance(obj, (int, str, bool)):
        return obj
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    try:
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        pass
    return obj


def insert_insights(rows: list[dict[str, Any]]) -> None:
    """Insert insight rows into analytics_insights. Caller ensures idempotency (insight_hash)."""
    if not rows:
        return
    client = get_client()
    table_id = f"{_project()}.{get_analytics_dataset()}.analytics_insights"
    sanitized = [_sanitize_for_json(r) for r in rows]
    errors = client.insert_rows_json(table_id, sanitized)
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
    try:
        df = client.query(q).to_dataframe()
    except Exception:
        return []
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
    min_created_date: Optional[date] = None,
) -> list[dict]:
    """List insights scoped by organization_id; no cross-tenant leakage. Use min_created_date for partition pruning."""
    # Local fallback: serve from JSON file when INSIGHTS_JSON_PATH is set (e.g. agents/output/insights_latest.json)
    json_path = os.environ.get("INSIGHTS_JSON_PATH")
    if json_path and os.path.isfile(json_path):
        try:
            import json
            with open(json_path) as f:
                rows = json.load(f)
            if not isinstance(rows, list):
                rows = [rows]
            out = []
            for r in rows:
                if (r.get("organization_id") or "") != organization_id:
                    continue
                if client_id is not None and r.get("client_id") != client_id:
                    continue
                if workspace_id and (r.get("workspace_id") or "") != workspace_id:
                    continue
                if status and (r.get("status") or "") != status:
                    continue
                if min_created_date and r.get("created_at"):
                    try:
                        from datetime import datetime
                        created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).date()
                        if created < min_created_date:
                            continue
                    except Exception:
                        pass
                out.append(r)
            out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
            return out[offset : offset + limit]
        except Exception:
            pass
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
    if min_created_date:
        where.append(f"DATE(created_at) >= '{min_created_date.isoformat()}'")
    if not where:
        where.append("1=1")
    q = f"""
    SELECT * FROM `{project}.{dataset}.analytics_insights`
    WHERE {' AND '.join(where)}
    ORDER BY created_at DESC
    LIMIT {limit} OFFSET {offset}
    """
    try:
        df = client.query(q).to_dataframe()
    except Exception as e:
        if _is_table_not_found(e):
            import logging
            logging.getLogger(__name__).debug("analytics_insights table not found; returning empty list")
            return []
        raise
    if df.empty:
        return []
    return [dict(row) for _, row in df.iterrows()]


def get_insight_by_id(insight_id: str, organization_id: Optional[str] = None) -> Optional[dict]:
    json_path = os.environ.get("INSIGHTS_JSON_PATH")
    if json_path and os.path.isfile(json_path):
        try:
            import json
            with open(json_path) as f:
                rows = json.load(f)
            if not isinstance(rows, list):
                rows = [rows]
            for r in rows:
                if r.get("insight_id") == insight_id:
                    if organization_id and (r.get("organization_id") or "") != organization_id:
                        continue
                    return r
            return None
        except Exception:
            pass
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
    except Exception as e:
        if _is_table_not_found(e):
            return None
        try:
            q_fallback = f"SELECT * FROM `{project}.{dataset}.analytics_insights` WHERE insight_id = '{esc(insight_id)}' LIMIT 1"
            df = client.query(q_fallback).to_dataframe()
        except Exception:
            raise e
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
    try:
        df = client.query(q).to_dataframe()
    except Exception:
        return None
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


def get_recent_insight_hashes(
    organization_id: str,
    client_id: str,
    since_days: int = 7,
) -> list[tuple[str, Any, str]]:
    """Return list of (insight_hash, created_at, severity) for repeat/cooldown detection."""
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()
    esc = (lambda s: (s or "").replace("'", "''"))
    cid = int(client_id) if client_id else 0
    q = f"""
    SELECT insight_hash, created_at, severity
    FROM `{project}.{dataset}.analytics_insights`
    WHERE organization_id = '{esc(organization_id)}' AND client_id = {cid}
      AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {since_days} DAY)
    ORDER BY created_at DESC
    """
    try:
        df = client.query(q).to_dataframe()
    except Exception:
        return []
    if df.empty:
        return []
    out = []
    for _, r in df.iterrows():
        h = r.get("insight_hash") or r.get("insight_id")
        if h:
            out.append((str(h), r.get("created_at"), str(r.get("severity") or "medium")))
    return out


def insert_executive_summary(
    organization_id: str,
    summary_date: date,
    top_risks: str,
    top_opportunities: str,
    overall_growth_state: str,
    recommended_focus_today: str,
    client_id: Optional[int] = None,
    workspace_id: Optional[str] = None,
) -> None:
    client = get_client()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    sid = str(uuid.uuid4())
    row = {
        "summary_id": sid,
        "organization_id": organization_id,
        "client_id": client_id,
        "workspace_id": workspace_id,
        "summary_date": summary_date.isoformat(),
        "top_risks": top_risks,
        "top_opportunities": top_opportunities,
        "overall_growth_state": overall_growth_state,
        "recommended_focus_today": recommended_focus_today,
        "created_at": now.isoformat(),
    }
    table_id = f"{_project()}.{get_analytics_dataset()}.executive_summaries"
    errors = client.insert_rows_json(table_id, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")


def get_latest_executive_summary(
    organization_id: str,
    client_id: Optional[int] = None,
    limit: int = 1,
) -> list[dict]:
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()
    esc = (lambda s: (s or "").replace("'", "''"))
    where = [f"organization_id = '{esc(organization_id)}'"]
    if client_id is not None:
        where.append(f"client_id = {client_id}")
    q = f"""
    SELECT * FROM `{project}.{dataset}.executive_summaries`
    WHERE {' AND '.join(where)}
    ORDER BY summary_date DESC
    LIMIT {limit}
    """
    try:
        df = client.query(q).to_dataframe()
    except Exception:
        return []
    if df.empty:
        return []
    return [dict(row) for _, row in df.iterrows()]


def insert_system_health(
    organization_id: str,
    agent_name: str,
    agent_runtime_seconds: float,
    failures: int = 0,
    insight_volume: int = 0,
    processing_latency_seconds: Optional[float] = None,
    status: str = "ok",
    details: Optional[str] = None,
) -> None:
    client = get_client()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    row = {
        "health_id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "check_time": now.isoformat(),
        "agent_name": agent_name,
        "agent_runtime_seconds": agent_runtime_seconds,
        "failures": failures,
        "insight_volume": insight_volume,
        "processing_latency_seconds": processing_latency_seconds or 0.0,
        "status": status,
        "details": details or "",
        "created_at": now.isoformat(),
    }
    table_id = f"{_project()}.{get_analytics_dataset()}.system_health"
    try:
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")
    except Exception:
        pass


def get_system_health_latest(
    organization_id: str,
    agent_name: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()
    esc = (lambda s: (s or "").replace("'", "''"))
    where = [f"organization_id = '{esc(organization_id)}'"]
    if agent_name:
        where.append(f"agent_name = '{esc(agent_name)}'")
    q = f"""
    SELECT * FROM `{project}.{dataset}.system_health`
    WHERE {' AND '.join(where)}
    ORDER BY check_time DESC
    LIMIT {limit}
    """
    try:
        df = client.query(q).to_dataframe()
    except Exception:
        return []
    if df.empty:
        return []
    return [dict(row) for _, row in df.iterrows()]


def update_decision_outcomes(
    history_id: str,
    outcome_metrics_after_7d: Optional[str] = None,
    outcome_metrics_after_30d: Optional[str] = None,
    confidence_score: Optional[float] = None,
) -> None:
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()
    esc = (lambda s: (s or "").replace("'", "''"))
    updates = []
    if outcome_metrics_after_7d is not None:
        updates.append(f"outcome_metrics_after_7d = '{esc(outcome_metrics_after_7d)}'")
    if outcome_metrics_after_30d is not None:
        updates.append(f"outcome_metrics_after_30d = '{esc(outcome_metrics_after_30d)}'")
    if confidence_score is not None:
        updates.append(f"confidence_score = {float(confidence_score)}")
    if not updates:
        return
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    updates.append(f"updated_at = '{now}'")
    q = f"""
    UPDATE `{project}.{dataset}.decision_history`
    SET {', '.join(updates)}
    WHERE history_id = '{esc(history_id)}'
    """
    client.query(q).result()


def get_decision_history_for_outcomes(
    organization_id: str,
    status: str = "applied",
    limit: int = 500,
) -> list[dict]:
    """Fetch applied decisions for outcome evaluation (need history_id, applied_at, insight_id)."""
    return get_decision_history(organization_id=organization_id, status=status, limit=limit)


def insert_audit_log(
    organization_id: str,
    event_type: str,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    payload: Optional[str] = None,
) -> None:
    client = get_client()
    project = _project()
    dataset = get_analytics_dataset()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    row = {
        "audit_id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "event_type": event_type,
        "entity_id": entity_id or "",
        "user_id": user_id or "",
        "payload": payload or "{}",
        "created_at": now.isoformat(),
    }
    table_id = f"{_project()}.{get_analytics_dataset()}.audit_log"
    try:
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")
    except Exception:
        pass
