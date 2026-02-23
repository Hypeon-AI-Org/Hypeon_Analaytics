"""
Insight Noise Suppression: prevent duplicate daily alerts, repeated insights, low-impact noise.
Uses cooldown_period, repeat_detection, impact_threshold, min_priority_score.
Same insight cannot reappear within cooldown days unless severity increases.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional

from .config_loader import get

DEFAULT_COOLDOWN_DAYS = 5
DEFAULT_MIN_PRIORITY = 0.05
DEFAULT_IMPACT_THRESHOLD = 0.01


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if hasattr(value, "timestamp"):
        return value
    try:
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def suppress_noise(
    insights: list[dict[str, Any]],
    *,
    cooldown_days: Optional[int] = None,
    min_priority_score: Optional[float] = None,
    impact_threshold: Optional[float] = None,
    existing_insight_hashes: Optional[Callable[[str, str], list[tuple[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    """
    Filter out:
    - Duplicates: same insight_hash within cooldown_period (unless severity increased).
    - Low priority: priority_score < min_priority_score.
    - Low impact: expected_impact_value < impact_threshold.
    existing_insight_hashes: optional (organization_id, client_id) -> list of (insight_hash, created_at, severity).
    """
    cooldown_days = cooldown_days if cooldown_days is not None else get("insight_cooldown_days", DEFAULT_COOLDOWN_DAYS)
    min_priority = min_priority_score if min_priority_score is not None else get("min_priority_score", DEFAULT_MIN_PRIORITY)
    impact_thresh = impact_threshold if impact_threshold is not None else get("impact_threshold", DEFAULT_IMPACT_THRESHOLD)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=cooldown_days)
    out = []

    for i in insights:
        priority = float(i.get("priority_score") or 0)
        impact_val = float(i.get("expected_impact_value") or 0)
        if priority < min_priority:
            continue
        if impact_val < impact_thresh:
            continue

        ih = (i.get("insight_hash") or i.get("insight_id") or "").strip()
        if not ih:
            out.append(i)
            continue

        org = str(i.get("organization_id") or "")
        client_id = i.get("client_id")
        severity = str(i.get("severity") or "medium")

        skip = False
        if existing_insight_hashes:
            existing = existing_insight_hashes(org, str(client_id or ""))
            severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            for (ex_hash, ex_created, ex_severity) in existing:
                if ex_hash != ih:
                    continue
                ex_dt = _parse_dt(ex_created)
                if ex_dt and ex_dt >= cutoff:
                    if severity_order.get(severity, 0) <= severity_order.get(str(ex_severity or "medium"), 0):
                        skip = True
                break
        if skip:
            continue
        out.append(i)
    return out
