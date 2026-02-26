"""
Copilot tools: definitions and executor for on-demand data fetching.
LLM calls tools only when needed; executor runs cache/BQ and returns JSON.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from typing import Any, Optional

# Tool definitions for LLM (name, description, parameters as JSON Schema)
# Claude and Gemini can both consume this format; adapt in each LLM client if needed.
COPILOT_TOOLS = [
    {
        "name": "get_business_overview",
        "description": "Get high-level business metrics: total revenue, total spend, blended ROAS, conversion rate, and 7-day trends. Use when the user asks about overall performance, how they are doing, or summary metrics.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_campaign_performance",
        "description": "Get campaign-level performance: campaign id, spend, revenue, ROAS, status (Scaling/Stable/Wasting). Use when the user asks about campaigns, which campaigns to scale or pause, or spend by campaign.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_funnel",
        "description": "Get funnel metrics: clicks, sessions, purchases, and drop percentages between stages. Use when the user asks about funnel, conversion funnel, or drop-off.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_actions",
        "description": "Get top recommended actions from insights: increase_budget, reduce_budget, investigate. Use when the user asks what to do, recommended actions, or next steps.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_decision_history",
        "description": "Get recent decisions applied: insight_id, recommended_action, status, applied_by, applied_at. Use when the user asks about past decisions or what was applied.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_google_ads_analysis",
        "description": "Get Google Ads performance: spend, clicks, impressions, conversions, revenue, ROAS, CTR, by campaign and device. Use when the user asks about Google Ads, paid search, or ad performance. Optionally restrict to last N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default 30).",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_google_analytics_analysis",
        "description": "Get Google Analytics (GA4) performance: sessions, conversions, revenue, conversion rate, by device. Use when the user asks about GA4, website analytics, or session/conversion data. Optionally restrict to last N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default 30).",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        },
    },
]


def _safe_div(a: float, b: float) -> float:
    if not b:
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


def _row_to_dict(row: Any) -> dict:
    """Convert DataFrame row (Series) or mapping to a plain dict for safe .get access."""
    if isinstance(row, dict):
        return row
    if hasattr(row, "to_dict"):
        return row.to_dict()
    if hasattr(row, "items"):
        return dict(row)
    return {}


def _normalize_tool_arguments(arguments: Any) -> dict:
    """Ensure tool arguments are always a dict (API may return a JSON string)."""
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def execute_tool(
    organization_id: str,
    client_id: int,
    tool_name: str,
    arguments: Optional[dict] = None,
) -> str:
    """
    Execute a Copilot tool and return JSON string result.
    Uses analytics cache and optional BQ/analysis helpers.
    """
    args = _normalize_tool_arguments(arguments)
    cid = int(client_id) if client_id is not None else 1

    if tool_name == "get_business_overview":
        from ..analytics_cache import get_cached_business_overview
        data = get_cached_business_overview(organization_id, cid)
        return json.dumps(data if data is not None else {})

    if tool_name == "get_campaign_performance":
        from ..analytics_cache import get_cached_campaign_performance
        items = get_cached_campaign_performance(organization_id, cid) or []
        return json.dumps({"items": items, "count": len(items)})

    if tool_name == "get_funnel":
        from ..analytics_cache import get_cached_funnel
        data = get_cached_funnel(organization_id, cid)
        return json.dumps(data if data is not None else {"clicks": 0, "sessions": 0, "purchases": 0, "drop_percentages": []})

    if tool_name == "get_actions":
        from ..analytics_cache import get_cached_actions
        items = get_cached_actions(organization_id, cid) or []
        return json.dumps({"items": items, "count": len(items)})

    if tool_name == "get_decision_history":
        try:
            from ..clients.bigquery import get_decision_history
            raw = get_decision_history(organization_id=organization_id, client_id=cid, status=None, limit=20)
            out = []
            for r in raw:
                row = {}
                for k, v in r.items():
                    row[k] = v.isoformat() if hasattr(v, "isoformat") else v
                out.append(row)
            return json.dumps({"items": out, "count": len(out)})
        except Exception:
            return json.dumps({"items": [], "count": 0})

    if tool_name == "get_google_ads_analysis":
        try:
            from ..clients.bigquery import load_ads_staging
            days = int(args.get("days") or 30)
            days = min(365, max(1, days))
            today = date.today()
            start = today - timedelta(days=days)
            df = load_ads_staging(client_id=cid, start_date=start, end_date=today, organization_id=organization_id)
            if df is None or df.empty:
                return json.dumps({"overview": {}, "by_campaign": [], "by_device": [], "daily_timeseries": []})
            total_spend = _safe_float(df["spend"].sum())
            total_clicks = _safe_float(df["clicks"].sum())
            total_impressions = _safe_float(df["impressions"].sum())
            total_conversions = _safe_float(df["conversions"].sum())
            total_revenue = _safe_float(df["revenue"].sum())
            overview = {
                "spend": round(total_spend, 2),
                "clicks": int(total_clicks),
                "impressions": int(total_impressions),
                "conversions": round(total_conversions, 2),
                "revenue": round(total_revenue, 2),
                "roas": round(_safe_div(total_revenue, total_spend), 2),
                "ctr": round(_safe_div(total_clicks, total_impressions) * 100, 2),
            }
            import pandas as pd
            camp = df.groupby("campaign_id", dropna=False).agg(
                spend=("spend", "sum"),
                revenue=("revenue", "sum"),
            ).reset_index()
            by_campaign = []
            for _, row in camp.iterrows():
                r = _row_to_dict(row)
                by_campaign.append({
                    "campaign_id": str(r.get("campaign_id") or ""),
                    "spend": round(_safe_float(r.get("spend")), 2),
                    "revenue": round(_safe_float(r.get("revenue")), 2),
                    "roas": round(_safe_div(_safe_float(r.get("revenue")), _safe_float(r.get("spend"))), 2),
                })
            by_campaign.sort(key=lambda x: x["spend"], reverse=True)
            dev = df.groupby("device", dropna=False).agg(spend=("spend", "sum"), conversions=("conversions", "sum")).reset_index()
            by_device = []
            for _, row in dev.iterrows():
                r = _row_to_dict(row)
                by_device.append({
                    "device": str(r.get("device") or "unknown"),
                    "spend": round(_safe_float(r.get("spend")), 2),
                    "conversions": round(_safe_float(r.get("conversions")), 2),
                })
            # Daily timeseries for Copilot graphs (match Analysis API shape)
            df["date"] = pd.to_datetime(df["date"])
            daily = df.groupby("date").agg(
                spend=("spend", "sum"),
                revenue=("revenue", "sum"),
            ).reset_index().sort_values("date")
            daily_ts = []
            for _, row in daily.iterrows():
                daily_ts.append({
                    "date": row["date"].strftime("%Y-%m-%d"),
                    "spend": round(_safe_float(row["spend"]), 2),
                    "revenue": round(_safe_float(row["revenue"]), 2),
                })
            return json.dumps({
                "overview": overview,
                "by_campaign": by_campaign[:15],
                "by_device": by_device,
                "daily_timeseries": daily_ts,
            })
        except Exception as e:
            return json.dumps({"error": str(e)[:200], "overview": {}, "by_campaign": [], "by_device": [], "daily_timeseries": []})

    if tool_name == "get_google_analytics_analysis":
        try:
            from ..clients.bigquery import load_ga4_staging
            days = int(args.get("days") or 30)
            days = min(365, max(1, days))
            today = date.today()
            start = today - timedelta(days=days)
            df = load_ga4_staging(client_id=cid, start_date=start, end_date=today, organization_id=organization_id)
            if df is None or df.empty:
                return json.dumps({"overview": {}, "by_device": [], "daily_timeseries": [], "conversion_funnel": []})
            total_sessions = _safe_float(df["sessions"].sum())
            total_conversions = _safe_float(df["conversions"].sum())
            total_revenue = _safe_float(df["revenue"].sum())
            overview = {
                "sessions": int(total_sessions),
                "conversions": round(total_conversions, 2),
                "revenue": round(total_revenue, 2),
                "conversion_rate": round(_safe_div(total_conversions, total_sessions) * 100, 2),
                "revenue_per_session": round(_safe_div(total_revenue, total_sessions), 2),
            }
            dev = df.groupby("device", dropna=False).agg(
                sessions=("sessions", "sum"),
                conversions=("conversions", "sum"),
                revenue=("revenue", "sum"),
            ).reset_index()
            by_device = []
            for _, row in dev.iterrows():
                r = _row_to_dict(row)
                by_device.append({
                    "device": str(r.get("device") or "unknown"),
                    "sessions": int(_safe_float(r.get("sessions"))),
                    "conversions": round(_safe_float(r.get("conversions")), 2),
                    "revenue": round(_safe_float(r.get("revenue")), 2),
                })
            # Daily timeseries for Copilot graphs
            import pandas as pd
            df["date"] = pd.to_datetime(df["date"])
            daily = df.groupby("date").agg(
                sessions=("sessions", "sum"),
                conversions=("conversions", "sum"),
                revenue=("revenue", "sum"),
            ).reset_index().sort_values("date")
            daily_ts = []
            for _, row in daily.iterrows():
                daily_ts.append({
                    "date": row["date"].strftime("%Y-%m-%d"),
                    "sessions": int(_safe_float(row["sessions"])),
                    "conversions": round(_safe_float(row["conversions"]), 2),
                    "revenue": round(_safe_float(row["revenue"]), 2),
                })
            conv_rate = _safe_div(total_conversions, total_sessions)
            conversion_funnel = [
                {"stage": "Sessions", "value": int(total_sessions), "drop_pct": None},
                {"stage": "Conversions", "value": round(total_conversions, 2), "drop_pct": round((1 - conv_rate) * 100, 1) if total_sessions else 0},
                {"stage": "Revenue", "value": round(total_revenue, 2), "drop_pct": None},
            ]
            return json.dumps({
                "overview": overview,
                "by_device": by_device,
                "daily_timeseries": daily_ts,
                "conversion_funnel": conversion_funnel,
            })
        except Exception as e:
            return json.dumps({"error": str(e)[:200], "overview": {}, "by_device": [], "daily_timeseries": [], "conversion_funnel": []})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
