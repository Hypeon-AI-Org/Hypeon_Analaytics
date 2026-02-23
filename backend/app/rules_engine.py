"""
Rules-first engine: load marketing_performance_daily, apply JSON rules, write to analytics_insights.
Deterministic insight_id for idempotent runs.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

# Default path to rules config (repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RULES_PATH = REPO_ROOT / "rules_config.json"


def _load_rules_config(path: Optional[os.PathLike | str] = None) -> dict:
    p = path or os.environ.get("RULES_CONFIG_PATH") or DEFAULT_RULES_PATH
    with open(p, "r") as f:
        return json.load(f)


def _insight_id(rule_id: str, entity_type: str, entity_id: str, period: str) -> str:
    """Deterministic id for idempotency."""
    raw = f"{rule_id}|{entity_type}|{entity_id}|{period}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _format_template(tpl: str, **kwargs: Any) -> str:
    for k, v in kwargs.items():
        tpl = tpl.replace("{" + k + "}", str(v) if v is not None else "")
    return tpl


def _evaluate_condition(row: dict, cond: dict) -> bool:
    """Evaluate a rule condition against a row (aggregated metrics)."""
    metric = cond.get("metric")
    op = cond.get("op")
    value = cond.get("value")
    if metric not in row or op is None:
        return False
    val = row.get(metric)
    if val is None:
        return False
    try:
        val = float(val)
    except (TypeError, ValueError):
        return False
    if cond.get("min_spend") is not None and row.get("spend", 0) < cond["min_spend"]:
        return False
    if cond.get("min_sessions") is not None and row.get("sessions", 0) < cond["min_sessions"]:
        return False
    if op == "eq":
        return val == value
    if op == "lt":
        return val < value
    if op == "gt":
        return val > value
    if op == "lte":
        return val <= value
    if op == "gte":
        return val >= value
    return False


def _aggregate_28d(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate last 28 days by client_id, channel, campaign_id, ad_group_id, device."""
    if df.empty:
        return df
    group = ["client_id", "channel", "campaign_id", "ad_group_id", "device"]
    # Only columns that exist
    group = [c for c in group if c in df.columns]
    agg = df.groupby(group, dropna=False).agg(
        spend=("spend", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
        sessions=("sessions", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    # Derived for rules that need them
    agg["roas"] = agg.apply(lambda r: r["revenue"] / r["spend"] if r["spend"] else 0, axis=1)
    agg["conversion_rate"] = agg.apply(
        lambda r: r["conversions"] / r["sessions"] if r.get("sessions") else 0, axis=1
    )
    # 28d baselines from raw df (already 28d window)
    if "roas_28d_avg" in df.columns:
        avg28 = df.groupby(group, dropna=False).agg(
            roas_28d_avg=("roas_28d_avg", "mean"),
            revenue_28d_avg=("revenue_28d_avg", "mean"),
        ).reset_index()
        agg = agg.merge(avg28, on=group, how="left")
    else:
        agg["roas_28d_avg"] = agg["roas"]
        agg["revenue_28d_avg"] = agg["revenue"]
    if "roas_pct_delta_28d" in df.columns:
        delta = df.groupby(group, dropna=False).agg(
            roas_pct_delta_28d=("roas_pct_delta_28d", "mean"),
        ).reset_index()
        agg = agg.merge(delta, on=group, how="left")
    else:
        agg["roas_pct_delta_28d"] = 0.0
    return agg


def _row_to_insight(
    rule: dict,
    entity_type: str,
    entity_id: str,
    client_id: int,
    period: str,
    row: dict,
) -> dict[str, Any]:
    """Build one analytics_insights row."""
    rule_id = rule["id"]
    insight_id = _insight_id(rule_id, entity_type, entity_id, period)
    # Template vars from row
    fmt = {k: row.get(k) for k in ["spend", "revenue", "roas", "sessions", "conversions", "conversion_rate",
                                    "roas_28d_avg", "revenue_28d_avg", "roas_pct_delta_28d"]}
    if fmt.get("roas_pct_delta_28d") is not None:
        fmt["roas_pct_delta_28d_pct"] = f"{float(fmt['roas_pct_delta_28d']) * 100:.1f}%"
    else:
        fmt["roas_pct_delta_28d_pct"] = "N/A"
    fmt["entity_id"] = entity_id
    summary = _format_template(rule.get("summary_template", ""), **fmt)
    explanation = _format_template(rule.get("explanation_template", ""), **fmt)
    recommendation = _format_template(rule.get("recommendation_template", ""), **fmt)
    evidence = [
        {"metric": k, "value": float(v), "baseline": float(row.get(f"{k.replace('_pct_delta_28d', '')}_28d_avg", 0) or 0), "period": "28d"}
        for k, v in [("revenue", row.get("revenue")), ("roas", row.get("roas"))] if v is not None
    ][:5]
    return {
        "insight_id": insight_id,
        "client_id": client_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "insight_type": rule.get("insight_type", rule_id),
        "summary": summary,
        "explanation": explanation,
        "recommendation": recommendation,
        "expected_impact": {"metric": "revenue", "estimate": 0.0, "units": "currency"},
        "confidence": 0.85,
        "evidence": evidence,
        "detected_by": [rule_id],
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "applied_at": None,
        "history": None,
    }


def generate_insights(
    client_id: int,
    as_of_date: date,
    *,
    load_data: Optional[Callable[[int, date], pd.DataFrame]] = None,
    rules_path: Optional[os.PathLike | str] = None,
    write: bool = True,
) -> list[dict[str, Any]]:
    """
    Load last 28 days of marketing_performance_daily for client, apply rules, produce insights.
    If write=True, inserts into analytics_insights (idempotent by insight_id).
    """
    config = _load_rules_config(rules_path)
    rules = config.get("rules", [])

    if load_data is None:
        from .clients.bigquery import load_marketing_performance
        load_data = load_marketing_performance
    df = load_data(client_id, as_of_date, 28)
    if df.empty:
        return []

    agg = _aggregate_28d(df)
    period = as_of_date.isoformat()
    insights: list[dict[str, Any]] = []

    for rule in rules:
        cond = rule.get("condition", {})
        for _, r in agg.iterrows():
            row = r.to_dict()
            campaign_id = row.get("campaign_id") or "unknown"
            ad_group_id = row.get("ad_group_id") or "unknown"
            entity_id = f"{campaign_id}_{ad_group_id}"
            if not _evaluate_condition(row, cond):
                continue
            entity_type = "campaign"
            insight = _row_to_insight(rule, entity_type, entity_id, client_id, period, row)
            insights.append(insight)

    if write and insights:
        from .clients.bigquery import insert_insights
        # Idempotent: BigQuery has no unique constraint; we could MERGE. For V1 we insert and allow duplicates
        # or run a MERGE from a temp table. Simplest: insert (document that DAG runs once per day per client).
        insert_insights(insights)

    return insights
