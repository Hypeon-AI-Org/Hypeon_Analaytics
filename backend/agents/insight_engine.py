"""
Insight Engine facade: single entry point for daily rule-based detection.
Calls rules_engine.generate_insights (loads marketing_performance_daily, applies rules, writes to analytics_insights).
Aligns with: Performance drop (roas_decline), Waste (waste_zero_revenue), Scaling (scale_opportunity), Funnel (funnel_leak).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional


def run_insight_engine(
    client_id: int,
    as_of_date: date,
    *,
    organization_id: str = "default",
    workspace_id: Optional[str] = None,
    write: bool = True,
    merge: bool = True,
    rank: bool = True,
    since_date: Optional[date] = None,
    load_data: Any = None,
    rules_path: Optional[str] = None,
) -> list[dict]:
    """
    Run rule-based insight generation for one client/date. Writes to analytics_insights when write=True.
    Returns list of insights (after merge/rank). Use from DAG or run_agents.
    """
    from backend.app.rules_engine import generate_insights
    return generate_insights(
        client_id,
        as_of_date,
        organization_id=organization_id,
        workspace_id=workspace_id,
        write=write,
        merge=merge,
        rank=rank,
        since_date=since_date,
        load_data=load_data,
        rules_path=rules_path,
    )
