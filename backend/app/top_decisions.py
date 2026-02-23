"""
Top Decisions Engine: Top N actions today for executives.
Ranking: priority = expected_impact * confidence * urgency * recency.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .config_loader import get
from .insight_ranker import compute_priority_score, rank_insights


def _urgency_weight(insight: dict) -> float:
    severity = (insight.get("severity") or "medium").lower()
    return {"critical": 1.5, "high": 1.3, "medium": 1.0, "low": 0.8}.get(severity, 1.0)


def top_decisions(
    insights: list[dict[str, Any]],
    *,
    top_n: Optional[int] = None,
    status_filter: Optional[str] = "new",
) -> list[dict[str, Any]]:
    """
    Return top N decisions (actions) ranked by expected_impact * confidence * urgency * recency.
    By default returns insights with status 'new' (actionable); pass status_filter=None for any.
    """
    top_n = top_n or get("top_decisions_n", 3)
    if status_filter is not None:
        insights = [i for i in insights if (i.get("status") or "").lower() == status_filter]
    if not insights:
        return []
    ranked = rank_insights(insights)
    for r in ranked:
        r["urgency_weight"] = _urgency_weight(r)
        r["action_priority"] = (r.get("priority_score") or 0) * r["urgency_weight"]
    ranked.sort(key=lambda x: (-(x.get("action_priority") or 0), str(x.get("created_at") or "")))
    return ranked[:top_n]
