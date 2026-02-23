"""
Centralized prioritization: priority_score = expected_impact * confidence * recency_weight * severity_weight.
Add rank; return top N actionable insights per client.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config_loader import get
from .impact_estimator import get_severity

SEVERITY_WEIGHT = {"low": 0.5, "medium": 1.0, "high": 1.5, "critical": 2.0}


def _recency_weight(created_at: Any) -> float:
    if created_at is None:
        return 1.0
    try:
        if hasattr(created_at, "timestamp"):
            ts = created_at.timestamp()
        else:
            ts = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).timestamp()
        age_days = (datetime.now(timezone.utc).timestamp() - ts) / 86400
        if age_days <= 1:
            return 1.0
        if age_days <= 7:
            return 0.9
        if age_days <= 28:
            return 0.7
        return 0.5
    except Exception:
        return 1.0


def _expected_impact_value(insight: dict) -> float:
    if insight.get("expected_impact_value") is not None:
        return float(insight["expected_impact_value"])
    ei = insight.get("expected_impact")
    if isinstance(ei, dict) and ei.get("estimate") is not None:
        return float(ei["estimate"])
    return 0.1


def compute_priority_score(insight: dict[str, Any]) -> float:
    impact = max(0.01, _expected_impact_value(insight))
    confidence = max(0.01, min(1.0, float(insight.get("confidence") or 0.5)))
    recency = _recency_weight(insight.get("created_at"))
    severity = get_severity(insight.get("insight_type") or "")
    sev_weight = SEVERITY_WEIGHT.get(severity, 1.0)
    return round(impact * confidence * recency * sev_weight, 6)


def rank_insights(insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute priority_score, severity, rank for each; sort by priority_score desc."""
    for i in insights:
        i["severity"] = get_severity(i.get("insight_type") or "")
        i["expected_impact_value"] = _expected_impact_value(i)
        i["priority_score"] = compute_priority_score(i)
    sorted_list = sorted(insights, key=lambda x: (-(x["priority_score"] or 0), str(x.get("created_at") or "")))
    for r, row in enumerate(sorted_list, 1):
        row["rank"] = r
    return sorted_list


def top_per_client(
    insights: list[dict[str, Any]],
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Return top N insights per client_id (default from config)."""
    top_n = top_n or get("top_insights_per_client", 5)
    ranked = rank_insights(insights)
    seen: set[tuple[str, int]] = set()
    out = []
    for r in ranked:
        key = (str(r.get("organization_id") or ""), int(r.get("client_id") or 0))
        count = sum(1 for x in out if (str(x.get("organization_id") or ""), int(x.get("client_id") or 0)) == key)
        if count < top_n:
            out.append(r)
    return out
