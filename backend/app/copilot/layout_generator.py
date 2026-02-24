"""
Copilot Layout Generator: dynamic_dashboard_generation, dynamic_report_creation, graph + table layouts.
Produces layout JSON consumable by frontend DynamicDashboardRenderer (kpi, chart, table, funnel).
"""
from __future__ import annotations

from typing import Any, Optional


def build_layout_from_context(
    context: dict,
    mode: str,
) -> dict:
    """
    Build a layout JSON from structured context. Mode: build_dashboard | build_report.
    Returns { "widgets": [ ... ] } suitable for DynamicDashboardRenderer and query contract validation.
    """
    widgets: list[dict] = []
    overview = context.get("overview") or {}
    campaigns = context.get("campaigns") or []
    funnel = context.get("funnel") or {}

    # KPIs from overview
    widgets.append({
        "type": "kpi",
        "title": "Total Revenue",
        "value": overview.get("total_revenue", 0),
        "trend": "up" if (overview.get("revenue_trend_7d") or 0) >= 0 else "down",
    })
    widgets.append({
        "type": "kpi",
        "title": "Total Spend",
        "value": overview.get("total_spend", 0),
        "trend": "up" if (overview.get("spend_trend_7d") or 0) >= 0 else "down",
    })
    widgets.append({
        "type": "kpi",
        "title": "Blended ROAS",
        "value": overview.get("blended_roas", 0),
    })
    widgets.append({
        "type": "kpi",
        "title": "Conversion Rate",
        "value": overview.get("conversion_rate", 0),
    })

    # Campaign table
    if campaigns:
        cols = [{"key": "campaign", "label": "Campaign"}, {"key": "spend", "label": "Spend"}, {"key": "revenue", "label": "Revenue"}, {"key": "roas", "label": "ROAS"}, {"key": "status", "label": "Status"}]
        rows = [{"campaign": c.get("campaign"), "spend": c.get("spend"), "revenue": c.get("revenue"), "roas": c.get("roas"), "status": c.get("status")} for c in campaigns[:20]]
        widgets.append({"type": "table", "title": "Campaign Performance", "columns": cols, "rows": rows})

    # Funnel
    if funnel.get("clicks") is not None or funnel.get("sessions") is not None or funnel.get("purchases") is not None:
        stages = []
        for name, val in [("Clicks", funnel.get("clicks")), ("Sessions", funnel.get("sessions")), ("Purchases", funnel.get("purchases"))]:
            if val is not None:
                drop = None
                if name == "Sessions" and funnel.get("drop_percentages"):
                    drop = funnel["drop_percentages"][0] if len(funnel["drop_percentages"]) > 0 else None
                elif name == "Purchases" and funnel.get("drop_percentages") and len(funnel["drop_percentages"]) > 1:
                    drop = funnel["drop_percentages"][1]
                stages.append({"name": name, "value": val, "dropPct": drop})
        if stages:
            widgets.append({"type": "funnel", "title": "Funnel", "stages": stages})

    return {"widgets": widgets}


def build_layout_from_llm_response(llm_layout: Any) -> Optional[dict]:
    """
    If the LLM returns a layout object, validate and return it. Otherwise return None.
    """
    if not llm_layout or not isinstance(llm_layout, dict):
        return None
    widgets = llm_layout.get("widgets") if isinstance(llm_layout.get("widgets"), list) else []
    return {"widgets": widgets}
