"""Tests for top_decisions engine."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from backend.app.top_decisions import top_decisions


def test_top_decisions_returns_top_n():
    insights = [
        {"insight_id": "a", "status": "new", "expected_impact_value": 0.9, "confidence": 0.9, "severity": "high", "created_at": "2025-02-22", "insight_type": "waste_zero_revenue"},
        {"insight_id": "b", "status": "new", "expected_impact_value": 0.5, "confidence": 0.5, "severity": "medium", "created_at": "2025-02-21", "insight_type": "roas_decline"},
        {"insight_id": "c", "status": "new", "expected_impact_value": 0.3, "confidence": 0.3, "severity": "low", "created_at": "2025-02-20", "insight_type": "scale_opportunity"},
    ]
    out = top_decisions(insights, top_n=2, status_filter="new")
    assert len(out) == 2
    assert out[0]["action_priority"] >= out[1]["action_priority"]


def test_top_decisions_filters_by_status():
    insights = [
        {"insight_id": "a", "status": "applied", "priority_score": 0.9},
        {"insight_id": "b", "status": "new", "priority_score": 0.5},
    ]
    out = top_decisions(insights, top_n=5, status_filter="new")
    assert len(out) == 1
    assert out[0]["insight_id"] == "b"
