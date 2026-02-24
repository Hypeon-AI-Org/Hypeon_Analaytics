"""
Copilot Context Builder: build a single structured context object per request.
No multi-query at runtime: data is loaded once (from cache preferred, then BQ only for decisions).
The Copilot facade ONLY consumes this object.
"""
from __future__ import annotations

from typing import Any, Optional


def build_context(
    organization_id: str,
    client_id: Optional[int] = None,
    insight_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build one structured context payload for the Copilot. Reads from analytics cache (overview, campaigns, funnel, actions)
    and optionally one BQ call for recent decision_history. Returns dict with overview, insights, decisions, funnel, campaigns.
    """
    from ..analytics_cache import (
        get_cached_business_overview,
        get_cached_campaign_performance,
        get_cached_funnel,
        get_cached_actions,
    )
    cid = int(client_id) if client_id is not None else 1
    overview = get_cached_business_overview(organization_id, cid) or {}
    campaigns = get_cached_campaign_performance(organization_id, cid) or []
    funnel = get_cached_funnel(organization_id, cid) or {}
    actions = get_cached_actions(organization_id, cid) or []

    # Recent decisions: single BQ call (only place Copilot path hits BQ if cache used for rest)
    decisions: list[dict] = []
    try:
        from ..clients.bigquery import get_decision_history
        decisions = get_decision_history(
            organization_id=organization_id,
            client_id=cid,
            status=None,
            limit=15,
        )
        decisions = [_serialize_row(r) for r in decisions]
    except Exception:
        pass

    # Top insights = actions list (already from cache)
    insights = [{"insight_id": a.get("insight_id"), "summary": a.get("summary"), "action": a.get("action")} for a in actions[:10]]

    context = {
        "overview": overview,
        "campaigns": campaigns,
        "funnel": funnel,
        "actions": actions,
        "insights": insights,
        "decisions": decisions,
    }
    if insight_id:
        context["focus_insight_id"] = insight_id
    return context


def _serialize_row(r: dict) -> dict:
    out = {}
    for k, v in r.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
