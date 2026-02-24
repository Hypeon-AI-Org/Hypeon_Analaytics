"""
Refresh analytics cache from BigQuery. Used by cache warmup on startup and by admin/refresh endpoint.
Computes business overview, campaign performance, funnel, and actions from marketing_performance_daily + analytics_insights.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from . import analytics_cache
from .analytics_cache import DEFAULT_CLIENT_ID


def _serialize_value(v) -> float | str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def do_refresh(
    organization_id: str = "default",
    client_id: Optional[int] = None,
) -> dict:
    """
    Load from BQ, compute aggregates, and fill analytics_cache for (organization_id, client_id).
    Returns summary dict with keys updated and any error message.
    """
    cid = int(client_id) if client_id is not None else DEFAULT_CLIENT_ID
    result: dict = {"organization_id": organization_id, "client_id": cid, "updated": [], "error": None}

    try:
        from .clients.bigquery import (
            load_marketing_performance,
            list_insights,
        )
        from .top_decisions import top_decisions
    except ImportError as e:
        result["error"] = str(e)
        return result

    today = date.today()

    # ----- Business overview -----
    try:
        df = load_marketing_performance(
            client_id=cid,
            as_of_date=today,
            days=28,
            organization_id=organization_id,
        )
        if df is not None and not df.empty:
            import pandas as pd
            df = df.copy()
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            cutoff_7 = pd.Timestamp(today - timedelta(days=7))
            cutoff_14 = pd.Timestamp(today - timedelta(days=14))
            last7 = df[df["date"] >= cutoff_7] if "date" in df.columns else df.tail(min(70, len(df)))
            prev7 = df[(df["date"] >= cutoff_14) & (df["date"] < cutoff_7)] if "date" in df.columns else None

            def sum_col(name):
                if name in last7.columns:
                    return last7[name].sum()
                return 0

            total_revenue_7d = sum_col("revenue")
            total_spend_7d = sum_col("spend")
            total_conversions_7d = sum_col("conversions")
            total_sessions_7d = sum_col("sessions")
            blended_roas = (total_revenue_7d / total_spend_7d) if total_spend_7d else 0
            conversion_rate = (total_conversions_7d / total_sessions_7d) if total_sessions_7d else 0

            revenue_trend_7d = 0.0
            spend_trend_7d = 0.0
            if prev7 is not None and not prev7.empty:
                prev_rev = prev7["revenue"].sum() if "revenue" in prev7.columns else 0
                prev_sp = prev7["spend"].sum() if "spend" in prev7.columns else 0
                if prev_rev:
                    revenue_trend_7d = (float(total_revenue_7d) - float(prev_rev)) / float(prev_rev)
                if prev_sp:
                    spend_trend_7d = (float(total_spend_7d) - float(prev_sp)) / float(prev_sp)

            overview = {
                "total_revenue": _serialize_value(total_revenue_7d),
                "total_spend": _serialize_value(total_spend_7d),
                "blended_roas": _serialize_value(blended_roas),
                "conversion_rate": _serialize_value(conversion_rate),
                "revenue_trend_7d": _serialize_value(revenue_trend_7d),
                "spend_trend_7d": _serialize_value(spend_trend_7d),
            }
            analytics_cache.refresh_cache_for_org_client(
                organization_id, cid,
                business_overview=overview,
            )
            result["updated"].append("business_overview")
    except Exception as e:
        result["error"] = result["error"] or str(e)

    # ----- Campaign performance -----
    try:
        df = load_marketing_performance(client_id=cid, as_of_date=today, days=14, organization_id=organization_id)
        if df is not None and not df.empty and "campaign_id" in df.columns:
            agg = df.groupby("campaign_id", dropna=False).agg(
                spend=("spend", "sum"),
                revenue=("revenue", "sum"),
            ).reset_index()
            agg["roas"] = agg.apply(lambda r: r["revenue"] / r["spend"] if r["spend"] else 0, axis=1)
            campaigns = []
            for _, row in agg.iterrows():
                roas = float(row.get("roas") or 0)
                if roas > 3:
                    status = "Scaling"
                elif roas > 1:
                    status = "Stable"
                else:
                    status = "Wasting"
                campaigns.append({
                    "campaign": str(row.get("campaign_id") or ""),
                    "spend": _serialize_value(row.get("spend")),
                    "revenue": _serialize_value(row.get("revenue")),
                    "roas": _serialize_value(roas),
                    "status": status,
                })
            analytics_cache.refresh_cache_for_org_client(
                organization_id, cid,
                campaign_performance=campaigns,
            )
            result["updated"].append("campaign_performance")
    except Exception as e:
        result["error"] = result["error"] or str(e)

    # ----- Funnel -----
    try:
        df = load_marketing_performance(client_id=cid, as_of_date=today, days=30, organization_id=organization_id)
        if df is not None and not df.empty:
            clicks = df["clicks"].sum() if "clicks" in df.columns else 0
            sessions = df["sessions"].sum() if "sessions" in df.columns else 0
            conversions = df["conversions"].sum() if "conversions" in df.columns else 0
            drop1 = (1 - sessions / clicks) if clicks else 0
            drop2 = (1 - conversions / sessions) if sessions else 0
            funnel = {
                "clicks": _serialize_value(clicks),
                "sessions": _serialize_value(sessions),
                "purchases": _serialize_value(conversions),
                "drop_percentages": [_serialize_value(drop1 * 100), _serialize_value(drop2 * 100)],
            }
            analytics_cache.refresh_cache_for_org_client(
                organization_id, cid,
                funnel=funnel,
            )
            result["updated"].append("funnel")
    except Exception as e:
        result["error"] = result["error"] or str(e)

    # ----- Actions (from insights + top_decisions) -----
    try:
        rows = list_insights(organization_id=organization_id, client_id=cid, status="new", limit=100)
        ranked = top_decisions(rows, top_n=10, status_filter="new")
        action_map = {
            "scale_opportunity": "increase_budget",
            "waste_zero_revenue": "reduce_budget",
            "roas_decline": "reduce_budget",
            "funnel_leak": "investigate",
            "anomaly": "investigate",
        }
        actions = []
        for r in ranked:
            it = (r.get("insight_type") or "").strip()
            action = action_map.get(it, "investigate")
            actions.append({
                "insight_id": r.get("insight_id"),
                "action": action,
                "summary": r.get("summary"),
                "confidence": _serialize_value(r.get("confidence")),
                "expected_impact": r.get("expected_impact_value"),
            })
        analytics_cache.refresh_cache_for_org_client(
            organization_id, cid,
            actions=actions,
        )
        result["updated"].append("actions")
    except Exception as e:
        result["error"] = result["error"] or str(e)

    return result
