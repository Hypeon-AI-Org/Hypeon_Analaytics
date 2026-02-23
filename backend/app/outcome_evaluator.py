"""
Outcome Feedback Loop: after insight marked APPLIED, compute metric_change_after_7d/30d and decision_success_score.
Updates decision_history; supports learning successful recommendation patterns.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional

from .clients.bigquery import (
    get_decision_history_for_outcomes,
    update_decision_outcomes,
)


def _compute_metric_change(
    client_id: int,
    insight_id: str,
    applied_at: datetime,
    window_days: int,
    load_metrics: Callable[[int, datetime, int], dict[str, float]],
) -> Optional[str]:
    """Return JSON string of metric deltas for the window after applied_at."""
    end = applied_at + timedelta(days=window_days)
    try:
        metrics = load_metrics(client_id, end, window_days)
        if metrics:
            return json.dumps(metrics)
    except Exception:
        pass
    return None


def _decision_success_score(
    outcome_7d: Optional[str],
    outcome_30d: Optional[str],
) -> float:
    """
    Simple success score 0–1 from outcome payloads.
    If outcome contains revenue_lift or roas_improvement, score higher.
    """
    score = 0.5
    for payload in (outcome_7d, outcome_30d):
        if not payload:
            continue
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
            if data.get("revenue_lift", 0) > 0 or data.get("roas_improvement", False):
                score = min(1.0, score + 0.25)
            if data.get("savings", 0) > 0:
                score = min(1.0, score + 0.1)
        except Exception:
            pass
    return round(score, 2)


def evaluate_outcomes(
    organization_id: str,
    *,
    load_metrics_for_period: Optional[Callable[[int, datetime, int], dict[str, float]]] = None,
    dry_run: bool = False,
) -> int:
    """
    For each applied decision past 7d (and 30d), compute outcome metrics and success score; update decision_history.
    Returns count of rows updated.
    """
    decisions = get_decision_history_for_outcomes(organization_id, status="applied", limit=500)
    now = datetime.now(timezone.utc)
    updated = 0

    for d in decisions:
        history_id = d.get("history_id")
        applied_at = d.get("applied_at")
        client_id = d.get("client_id")
        insight_id = d.get("insight_id")
        if not history_id or not applied_at:
            continue
        if hasattr(applied_at, "timestamp"):
            applied_dt = applied_at
        else:
            try:
                applied_dt = datetime.fromisoformat(str(applied_at).replace("Z", "+00:00"))
            except Exception:
                continue

        outcome_7d = d.get("outcome_metrics_after_7d")
        outcome_30d = d.get("outcome_metrics_after_30d")

        if load_metrics_for_period and client_id is not None:
            if (now - applied_dt).days >= 7 and not outcome_7d:
                outcome_7d = _compute_metric_change(
                    int(client_id), insight_id or "", applied_dt, 7, load_metrics_for_period
                )
            if (now - applied_dt).days >= 30 and not outcome_30d:
                outcome_30d = _compute_metric_change(
                    int(client_id), insight_id or "", applied_dt, 30, load_metrics_for_period
                )

        score = _decision_success_score(outcome_7d, outcome_30d)
        # Store success_score in outcome_30d JSON when we have 30d outcome
        if outcome_30d:
            try:
                data = json.loads(outcome_30d) if isinstance(outcome_30d, str) else dict(outcome_30d)
                data["decision_success_score"] = score
                outcome_30d = json.dumps(data)
            except Exception:
                pass
        if dry_run:
            updated += 1
            continue
        try:
            update_decision_outcomes(
                history_id,
                outcome_metrics_after_7d=outcome_7d,
                outcome_metrics_after_30d=outcome_30d,
            )
            updated += 1
        except Exception:
            pass
    return updated
