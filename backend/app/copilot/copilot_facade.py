"""
Copilot Facade: free-form query, single structured context (no multi-query), mode routing, optional layout.
Uses context_builder once, mode_router, layout_generator; returns summary, top_drivers, recommended_actions, confidence, layout.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from .context_builder import build_context
from .layout_generator import build_layout_from_context
from .mode_router import route_copilot_mode
from .query_contract import validate_layout


def query_copilot(
    query: str,
    organization_id: str,
    *,
    client_id: Optional[int] = None,
    session_id: Optional[str] = None,
    insight_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run Copilot: build context once, route mode, build response (and optional layout for build_dashboard/build_report).
    Returns { summary, top_drivers, recommended_actions, confidence, layout?, mode }.
    """
    # Single context load
    context = build_context(organization_id, client_id=client_id, insight_id=insight_id)
    mode = route_copilot_mode(query, insight_id=insight_id)

    # Optional session memory
    if session_id:
        from .session_memory import get_session_store
        store = get_session_store()
        store.append(organization_id, session_id, "user", query)
        prev = store.get_context_summary(organization_id, session_id)
        if prev:
            context["_session_previous"] = prev

    # Build response from context (no LLM call in Phase 1 for v1/copilot path - we return structured from context)
    overview = context.get("overview") or {}
    actions = context.get("actions") or []
    summary = _summarize_from_context(overview, actions)
    top_drivers = _drivers_from_context(overview, context.get("campaigns"))
    recommended_actions = [{"action": a.get("action"), "summary": a.get("summary"), "confidence": a.get("confidence")} for a in actions[:5]]
    confidence = 0.85

    out = {
        "summary": summary,
        "top_drivers": top_drivers,
        "recommended_actions": recommended_actions,
        "confidence": confidence,
        "mode": mode,
    }

    # Layout for build_dashboard / build_report
    if mode in ("build_dashboard", "build_report"):
        layout = build_layout_from_context(context, mode)
        valid, errs = validate_layout(layout)
        if valid:
            out["layout"] = layout
        else:
            out["layout_errors"] = errs

    if session_id:
        from .session_memory import get_session_store
        get_session_store().set_context_summary(organization_id, session_id, {"summary": summary, "mode": mode})

    return out


def _summarize_from_context(overview: dict, actions: list) -> str:
    rev = overview.get("total_revenue") or 0
    sp = overview.get("total_spend") or 0
    roas = overview.get("blended_roas") or 0
    parts = [f"Revenue: {rev}, Spend: {sp}, ROAS: {roas}."]
    if actions:
        parts.append(f" {len(actions)} recommended actions.")
    return " ".join(parts)


def _drivers_from_context(overview: dict, campaigns: list) -> list[str]:
    drivers = []
    if overview.get("revenue_trend_7d") is not None:
        t = overview["revenue_trend_7d"]
        drivers.append(f"Revenue trend 7d: {'up' if (t or 0) >= 0 else 'down'}")
    if campaigns:
        by_status = {}
        for c in campaigns:
            s = c.get("status") or "Unknown"
            by_status[s] = by_status.get(s, 0) + 1
        for s, n in by_status.items():
            drivers.append(f"{n} campaign(s) {s}")
    return drivers[:5]
