"""
Copilot Layout Generator: dynamic_dashboard_generation, dynamic_report_creation, graph + table layouts.
Validates widget types and datasets before return; rejects invalid layout to avoid frontend crash.
"""
from __future__ import annotations

from typing import Any, Optional

from .query_contract import validate_layout

VALID_WIDGET_TYPES = frozenset(("kpi", "chart", "table", "funnel"))


def is_layout_empty_or_all_zeros(layout: Optional[dict]) -> bool:
    """
    True if layout should not be shown: no widgets, or only KPI widgets with all zero/empty values
    (no table, chart, or funnel with data). Used to avoid showing the graph block when data is not available.
    """
    if not layout or not isinstance(layout, dict):
        return True
    widgets = layout.get("widgets") or []
    if not widgets:
        return True
    has_meaningful = False
    all_kpis_zero = True
    for w in widgets:
        if not isinstance(w, dict):
            continue
        t = w.get("type")
        if t == "table":
            rows = w.get("rows") or []
            if rows:
                has_meaningful = True
                break
        if t == "chart":
            data = w.get("data") or []
            if data:
                has_meaningful = True
                break
        if t == "funnel":
            stages = w.get("stages") or []
            if stages:
                has_meaningful = True
                break
        if t == "kpi":
            val = w.get("value")
            if val is None:
                continue
            try:
                if float(val) != 0:
                    all_kpis_zero = False
                    break
            except (TypeError, ValueError):
                if str(val).strip():
                    all_kpis_zero = False
                    break
    if has_meaningful:
        return False
    # Only KPIs and they're all zero (or no non-KPI widgets with data)
    return all_kpis_zero


def _validate_widget_type(w: Any) -> bool:
    if not isinstance(w, dict):
        return False
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


def _sanitize_widget(w: Any) -> dict:
    """Ensure widget has valid shape; drop invalid fields."""
    if not isinstance(w, dict):
        return {}
    t = w.get("type")
    if t == "table":
        columns = []
        for i, c in enumerate(w.get("columns") or []):
            if isinstance(c, dict) and c.get("key"):
                columns.append(c)
            else:
                label = str(c.get("label", c)) if isinstance(c, dict) else str(c)
                columns.append({"key": str(i), "label": label})
        rows = []
        for r in (w.get("rows") or []):
            if isinstance(r, dict):
                rows.append(r)
            elif isinstance(r, (list, tuple)):
                rows.append({str(i): v for i, v in enumerate(r)})
            else:
                rows.append({})
        return {
            "type": "table",
            "title": w.get("title"),
            "columns": columns,
            "rows": rows,
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

    def _has_value(v: Any) -> bool:
        if v is None:
            return False
        try:
            return float(v) != 0
        except (TypeError, ValueError):
            return bool(v)

    overview_has_data = (
        _has_value(overview.get("total_revenue"))
        or _has_value(overview.get("total_spend"))
        or _has_value(overview.get("blended_roas"))
        or _has_value(overview.get("conversion_rate"))
    )
    funnel_has_data = (
        funnel.get("clicks") is not None
        or funnel.get("sessions") is not None
        or funnel.get("purchases") is not None
    )

    # KPIs: use exact metrics from the source that has data (overview or funnel)
    if overview_has_data:
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
    elif funnel_has_data:
        # Use exact metrics from funnel source when overview has no data
        clicks = funnel.get("clicks")
        sessions = funnel.get("sessions")
        purchases = funnel.get("purchases")
        if clicks is not None:
            widgets.append({"type": "kpi", "title": "Clicks", "value": clicks})
        if sessions is not None:
            widgets.append({"type": "kpi", "title": "Sessions", "value": sessions})
        if purchases is not None:
            widgets.append({"type": "kpi", "title": "Purchases", "value": purchases})
        if sessions is not None and purchases is not None:
            try:
                s, p = float(sessions), float(purchases)
                conv_rate = (p / s * 100) if s else 0
                widgets.append({"type": "kpi", "title": "Conversion Rate %", "value": round(conv_rate, 2)})
            except (TypeError, ValueError):
                pass

    # Campaign table and bar chart (actual graph from business/campaign data)
    if campaigns:
        cols = [{"key": "campaign", "label": "Campaign"}, {"key": "spend", "label": "Spend"}, {"key": "revenue", "label": "Revenue"}, {"key": "roas", "label": "ROAS"}, {"key": "status", "label": "Status"}]
        rows = []
        chart_data = []
        for c in campaigns[:20]:
            if not isinstance(c, dict):
                continue
            rows.append({
                "campaign": c.get("campaign"),
                "spend": c.get("spend"),
                "revenue": c.get("revenue"),
                "roas": c.get("roas"),
                "status": c.get("status"),
            })
            # Build chart data (top 12 for readability): campaign name, spend, revenue
            if len(chart_data) < 12:
                try:
                    spend_val = float(c.get("spend") or 0) if c.get("spend") is not None else 0
                    rev_val = float(c.get("revenue") or 0) if c.get("revenue") is not None else 0
                except (TypeError, ValueError):
                    spend_val, rev_val = 0, 0
                chart_data.append({
                    "campaign": str(c.get("campaign") or "")[:20] or "—",
                    "spend": spend_val,
                    "revenue": rev_val,
                })
        if rows:
            widgets.append({"type": "table", "title": "Campaign Performance", "columns": cols, "rows": rows})
        if chart_data:
            widgets.append({
                "type": "chart",
                "chartType": "bar",
                "title": "Campaign Spend",
                "data": chart_data,
                "xKey": "campaign",
                "yKey": "spend",
            })

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


def _build_ga_layout(ga_result: dict) -> dict:
    """Build layout from get_google_analytics_analysis tool result (GA4: sessions, conversions, daily trends, by device, funnel)."""
    widgets: list[dict] = []
    overview = ga_result.get("overview") or {}
    by_device = ga_result.get("by_device") or []
    daily_ts = ga_result.get("daily_timeseries") or []
    conversion_funnel = ga_result.get("conversion_funnel") or []
    widgets.append({
        "type": "kpi",
        "title": "Sessions",
        "value": overview.get("sessions", 0),
    })
    widgets.append({
        "type": "kpi",
        "title": "Conversions",
        "value": overview.get("conversions", 0),
    })
    widgets.append({
        "type": "kpi",
        "title": "Revenue",
        "value": overview.get("revenue", 0),
    })
    widgets.append({
        "type": "kpi",
        "title": "Conversion Rate %",
        "value": overview.get("conversion_rate", 0),
    })
    if daily_ts:
        widgets.append({
            "type": "chart",
            "chartType": "line",
            "title": "Daily Trends (Sessions)",
            "data": daily_ts,
            "xKey": "date",
            "yKey": "sessions",
        })
    if conversion_funnel:
        stages = []
        for s in conversion_funnel:
            if isinstance(s, dict) and "stage" in s and "value" in s:
                stages.append({
                    "name": str(s["stage"]),
                    "value": s["value"],
                    "dropPct": s.get("drop_pct"),
                })
        if stages:
            widgets.append({"type": "funnel", "title": "Conversion Funnel", "stages": stages})
    if by_device:
        cols = [{"key": "device", "label": "Device"}, {"key": "sessions", "label": "Sessions"}, {"key": "conversions", "label": "Conversions"}, {"key": "revenue", "label": "Revenue"}]
        rows = [{"device": d.get("device"), "sessions": d.get("sessions"), "conversions": d.get("conversions"), "revenue": d.get("revenue")} for d in by_device if isinstance(d, dict)]
        if rows:
            widgets.append({"type": "table", "title": "GA4 by Device", "columns": cols, "rows": rows})
        bar_data = [{"device": str(d.get("device") or ""), "sessions": int(d.get("sessions") or 0)} for d in by_device if isinstance(d, dict)]
        if bar_data:
            widgets.append({"type": "chart", "chartType": "bar", "title": "Sessions by Device", "data": bar_data, "xKey": "device", "yKey": "sessions"})
    layout = {"widgets": widgets}
    valid, _ = validate_layout(layout)
    if not valid:
        return {"widgets": []}
    return {"widgets": [_sanitize_widget(w) for w in widgets if _validate_widget_type(w)]}


def _build_ads_layout(ads_result: dict) -> dict:
    """Build layout from get_google_ads_analysis tool result (spend, revenue, ROAS, daily trends, by campaign/device)."""
    widgets: list[dict] = []
    overview = ads_result.get("overview") or {}
    by_campaign = ads_result.get("by_campaign") or []
    by_device = ads_result.get("by_device") or []
    daily_ts = ads_result.get("daily_timeseries") or []
    widgets.append({
        "type": "kpi",
        "title": "Spend",
        "value": overview.get("spend", 0),
    })
    widgets.append({
        "type": "kpi",
        "title": "Revenue",
        "value": overview.get("revenue", 0),
    })
    widgets.append({
        "type": "kpi",
        "title": "ROAS",
        "value": overview.get("roas", 0),
    })
    widgets.append({
        "type": "kpi",
        "title": "CTR %",
        "value": overview.get("ctr", 0),
    })
    if daily_ts:
        widgets.append({
            "type": "chart",
            "chartType": "line",
            "title": "Daily Spend",
            "data": daily_ts,
            "xKey": "date",
            "yKey": "spend",
        })
    if by_campaign:
        cols = [{"key": "campaign_id", "label": "Campaign"}, {"key": "spend", "label": "Spend"}, {"key": "revenue", "label": "Revenue"}, {"key": "roas", "label": "ROAS"}]
        rows = [{"campaign_id": c.get("campaign_id"), "spend": c.get("spend"), "revenue": c.get("revenue"), "roas": c.get("roas")} for c in by_campaign[:15] if isinstance(c, dict)]
        if rows:
            widgets.append({"type": "table", "title": "Google Ads by Campaign", "columns": cols, "rows": rows})
        bar_data = [{"campaign_id": str(c.get("campaign_id") or "")[:18], "spend": float(c.get("spend") or 0)} for c in by_campaign[:10] if isinstance(c, dict)]
        if bar_data:
            widgets.append({"type": "chart", "chartType": "bar", "title": "Spend by Campaign", "data": bar_data, "xKey": "campaign_id", "yKey": "spend"})
    if by_device:
        cols = [{"key": "device", "label": "Device"}, {"key": "spend", "label": "Spend"}, {"key": "conversions", "label": "Conversions"}]
        rows = [{"device": d.get("device"), "spend": d.get("spend"), "conversions": d.get("conversions")} for d in by_device if isinstance(d, dict)]
        if rows:
            widgets.append({"type": "table", "title": "Google Ads by Device", "columns": cols, "rows": rows})
        bar_data = [{"device": str(d.get("device") or ""), "spend": float(d.get("spend") or 0)} for d in by_device if isinstance(d, dict)]
        if bar_data:
            widgets.append({"type": "chart", "chartType": "bar", "title": "Spend by Device", "data": bar_data, "xKey": "device", "yKey": "spend"})
    layout = {"widgets": widgets}
    valid, _ = validate_layout(layout)
    if not valid:
        return {"widgets": []}
    return {"widgets": [_sanitize_widget(w) for w in widgets if _validate_widget_type(w)]}


def build_layout_from_tool_results(
    tool_results: dict[str, Any],
    organization_id: str,
    client_id: int,
) -> Optional[dict]:
    """
    Build a layout relevant to what the user asked, from the last round of tool results.
    - If get_google_analytics_analysis was called -> GA4 layout (sessions, conversions, by device).
    - Else if get_google_ads_analysis was called -> Google Ads layout (spend, ROAS, by campaign/device).
    - Else -> overview dashboard from get_business_overview / get_campaign_performance / get_funnel, or None.
    """
    if not tool_results:
        return None
    # Prefer GA-specific layout when user asked about GA4 / Google Analytics
    ga_result = tool_results.get("get_google_analytics_analysis")
    if isinstance(ga_result, dict) and not ga_result.get("error"):
        out = _build_ga_layout(ga_result)
        if out.get("widgets"):
            return out
    # Else prefer Ads-specific layout when user asked about Google Ads
    ads_result = tool_results.get("get_google_ads_analysis")
    if isinstance(ads_result, dict) and not ads_result.get("error"):
        out = _build_ads_layout(ads_result)
        if out.get("widgets"):
            return out
    # Else overview dashboard from cache-backed tools (what to do, summary, campaigns, funnel)
    overview = tool_results.get("get_business_overview") or {}
    campaigns = (tool_results.get("get_campaign_performance") or {}).get("items", [])
    funnel = tool_results.get("get_funnel") or {}
    if isinstance(overview, dict) or campaigns or (isinstance(funnel, dict) and (funnel.get("clicks") is not None or funnel.get("sessions") is not None or funnel.get("purchases") is not None)):
        context = {
            "overview": overview if isinstance(overview, dict) else {},
            "campaigns": campaigns if isinstance(campaigns, list) else [],
            "funnel": funnel if isinstance(funnel, dict) else {},
        }
        return build_layout_from_context(context, "build_dashboard")
    return None


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
