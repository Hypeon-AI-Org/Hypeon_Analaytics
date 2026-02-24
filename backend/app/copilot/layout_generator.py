"""
Copilot Layout Generator: dynamic_dashboard_generation, dynamic_report_creation, graph + table layouts.
Validates widget types and datasets before return; rejects invalid layout to avoid frontend crash.
"""
from __future__ import annotations

from typing import Any, Optional

from .query_contract import validate_layout

VALID_WIDGET_TYPES = frozenset(("kpi", "chart", "table", "funnel"))


def _validate_widget_type(w: dict) -> bool:
    t = w.get("type")
    if t not in VALID_WIDGET_TYPES:
        return False
    if t == "table" and ("columns" not in w or "rows" not in w):
        return False
    if t == "chart" and "data" not in w:
        return False
    if t == "funnel" and "stages" not in w:
        return False
    return True


def _sanitize_widget(w: dict) -> dict:
    """Ensure widget has valid shape; drop invalid fields."""
    t = w.get("type")
    if t == "table":
        return {
            "type": "table",
            "title": w.get("title"),
            "columns": [c if isinstance(c, dict) and c.get("key") else {"key": str(i), "label": str(c.get("label", ""))} for i, c in enumerate(w.get("columns") or [])],
            "rows": [r if isinstance(r, dict) else {} for r in (w.get("rows") or [])],
        }
    if t == "chart":
        return {
            "type": "chart",
            "chartType": w.get("chartType") if w.get("chartType") in ("line", "bar", "pie") else "bar",
            "title": w.get("title"),
            "data": list(w.get("data") or []) if isinstance(w.get("data"), list) else [],
            "xKey": w.get("xKey"),
            "yKey": w.get("yKey"),
        }
    if t == "funnel":
        stages = []
        for s in w.get("stages") or []:
            if isinstance(s, dict) and "name" in s and "value" in s:
                stages.append({"name": str(s["name"]), "value": s["value"], "dropPct": s.get("dropPct")})
        return {"type": "funnel", "title": w.get("title"), "stages": stages}
    if t == "kpi":
        return {
            "type": "kpi",
            "title": str(w.get("title", "")),
            "value": w.get("value", ""),
            "trend": w.get("trend") if w.get("trend") in ("up", "down", "neutral") else None,
            "subtitle": w.get("subtitle"),
        }
    return w


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

    layout = {"widgets": widgets}
    valid, errors = validate_layout(layout)
    if not valid:
        return {"widgets": []}
    sanitized = []
    for w in layout["widgets"]:
        if not _validate_widget_type(w):
            continue
        sanitized.append(_sanitize_widget(w))
    return {"widgets": sanitized}


def build_layout_from_llm_response(llm_layout: Any) -> Optional[dict]:
    """
    If the LLM returns a layout object, validate widget types and datasets, then return.
    Rejects invalid layout to avoid frontend crash. Returns None if invalid.
    """
    if not llm_layout or not isinstance(llm_layout, dict):
        return None
    raw_widgets = llm_layout.get("widgets") if isinstance(llm_layout.get("widgets"), list) else []
    widgets = []
    for w in raw_widgets:
        if not isinstance(w, dict) or not _validate_widget_type(w):
            continue
        widgets.append(_sanitize_widget(w))
    layout = {"widgets": widgets}
    valid, _ = validate_layout(layout)
    if not valid:
        return None
    return layout
