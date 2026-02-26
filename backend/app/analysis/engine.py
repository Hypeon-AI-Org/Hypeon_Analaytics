"""
Analysis Engine: compute ROAS, revenue trends, spend trends, growth %, summaries.
Uses pandas only. No LLM. Output: summary_stats, table (list of dicts), chart_data (for viz).
"""
from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd


def _safe_div(a: float, b: float) -> float:
    if b is None or b == 0 or (isinstance(b, float) and math.isnan(b)):
        return 0.0
    r = a / b
    return 0.0 if (math.isnan(r) or math.isinf(r)) else r


def _safe_float(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        f = float(v)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return 0.0


def run_analysis(
    df: pd.DataFrame,
    *,
    analysis_type: str = "campaign_performance",
    date_column: str = "date",
) -> dict[str, Any]:
    """
    Run analysis on a DataFrame produced by tools (campaign_performance, channel_breakdown, period_comparison).
    Returns { summary_stats, table, chart_data }.
    - summary_stats: dict of aggregates (total_revenue, total_spend, roas, growth_pct, etc.)
    - table: list of dicts (rows) for tabular display
    - chart_data: list of series suitable for visualization (e.g. time series or breakdown)
    """
    if df is None or df.empty:
        return _empty_result(analysis_type)

    df = df.copy()
    out: dict[str, Any] = {"summary_stats": {}, "table": [], "chart_data": []}

    if analysis_type == "campaign_performance":
        return _analyze_campaign_performance(df, out)
    if analysis_type == "channel_breakdown":
        return _analyze_channel_breakdown(df, out)
    if analysis_type == "period_comparison":
        return _analyze_period_comparison(df, out, date_column)

    out["summary_stats"] = {"error": "unknown_analysis_type", "analysis_type": analysis_type}
    return out


def _empty_result(analysis_type: str) -> dict[str, Any]:
    return {
        "summary_stats": {"data_available": False, "analysis_type": analysis_type},
        "table": [],
        "chart_data": [],
    }


def _analyze_campaign_performance(df: pd.DataFrame, out: dict[str, Any]) -> dict[str, Any]:
    total_spend = _safe_float(df["spend"].sum()) if "spend" in df.columns else 0.0
    total_revenue = _safe_float(df["revenue"].sum()) if "revenue" in df.columns else 0.0
    total_conversions = _safe_float(df["conversions"].sum()) if "conversions" in df.columns else 0.0
    total_clicks = _safe_float(df["clicks"].sum()) if "clicks" in df.columns else 0.0

    out["summary_stats"] = {
        "total_spend": round(total_spend, 2),
        "total_revenue": round(total_revenue, 2),
        "roas": round(_safe_div(total_revenue, total_spend), 2),
        "total_conversions": round(total_conversions, 2),
        "total_clicks": int(total_clicks),
        "campaign_count": len(df),
        "data_available": True,
    }
    out["table"] = _df_to_table_rows(df, ["campaign_id", "channel", "spend", "revenue", "roas", "clicks", "conversions"])
    out["chart_data"] = df.to_dict("records") if not df.empty else []
    return out


def _analyze_channel_breakdown(df: pd.DataFrame, out: dict[str, Any]) -> dict[str, Any]:
    total_spend = _safe_float(df["spend"].sum()) if "spend" in df.columns else 0.0
    total_revenue = _safe_float(df["revenue"].sum()) if "revenue" in df.columns else 0.0
    total_conversions = _safe_float(df["conversions"].sum()) if "conversions" in df.columns else 0.0

    out["summary_stats"] = {
        "total_spend": round(total_spend, 2),
        "total_revenue": round(total_revenue, 2),
        "roas": round(_safe_div(total_revenue, total_spend), 2),
        "total_conversions": round(total_conversions, 2),
        "channel_count": len(df),
        "data_available": True,
    }
    out["table"] = _df_to_table_rows(df, ["channel", "spend", "revenue", "roas", "clicks", "conversions"])
    out["chart_data"] = df.to_dict("records") if not df.empty else []
    return out


def _analyze_period_comparison(
    df: pd.DataFrame,
    out: dict[str, Any],
    date_column: str,
) -> dict[str, Any]:
    if "period_label" not in df.columns:
        out["summary_stats"] = {"data_available": False, "reason": "no_period_label"}
        return out

    periods = df["period_label"].dropna().unique().tolist()
    summary_by_period = []
    for p in periods:
        sub = df[df["period_label"] == p]
        spend = _safe_float(sub["spend"].sum()) if "spend" in sub.columns else 0.0
        revenue = _safe_float(sub["revenue"].sum()) if "revenue" in sub.columns else 0.0
        conv = _safe_float(sub["conversions"].sum()) if "conversions" in sub.columns else 0.0
        summary_by_period.append({
            "period_label": p,
            "spend": round(spend, 2),
            "revenue": round(revenue, 2),
            "conversions": round(conv, 2),
            "roas": round(_safe_div(revenue, spend), 2),
        })
    out["table"] = summary_by_period
    out["chart_data"] = df.to_dict("records") if not df.empty else []

    # Growth % between first two periods
    growth_pct = None
    if len(summary_by_period) >= 2:
        a, b = summary_by_period[0], summary_by_period[1]
        rev_a, rev_b = a.get("revenue", 0), b.get("revenue", 0)
        sp_a, sp_b = a.get("spend", 0), b.get("spend", 0)
        if rev_b and rev_b != 0:
            growth_pct = round((rev_a - rev_b) / rev_b * 100, 1)
        out["summary_stats"]["revenue_growth_pct"] = growth_pct
        if sp_b and sp_b != 0:
            out["summary_stats"]["spend_growth_pct"] = round((sp_a - sp_b) / sp_b * 100, 1)

    out["summary_stats"]["data_available"] = True
    out["summary_stats"]["periods"] = periods
    return out


def _df_to_table_rows(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    out = []
    for _, row in df.iterrows():
        r = {}
        for c in columns:
            if c in df.columns:
                v = row.get(c)
                if isinstance(v, (int, float)) and math.isnan(v):
                    v = 0
                if isinstance(v, float) and not math.isnan(v):
                    r[c] = round(v, 2) if c not in ("clicks", "impressions") else int(v)
                else:
                    r[c] = v
        out.append(r)
    return out[:500]
