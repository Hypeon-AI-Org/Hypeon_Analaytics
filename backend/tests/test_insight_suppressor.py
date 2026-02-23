"""Tests for insight_suppressor."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from backend.app.insight_suppressor import suppress_noise


def test_suppress_low_priority():
    insights = [
        {"insight_id": "1", "insight_hash": "h1", "priority_score": 0.01, "expected_impact_value": 0.5},
        {"insight_id": "2", "insight_hash": "h2", "priority_score": 0.9, "expected_impact_value": 0.5},
    ]
    out = suppress_noise(insights, min_priority_score=0.05)
    assert len(out) == 1
    assert out[0]["insight_id"] == "2"


def test_suppress_no_existing_hashes():
    insights = [
        {"insight_id": "1", "insight_hash": "h1", "priority_score": 0.9, "expected_impact_value": 0.2, "organization_id": "o", "client_id": 1, "severity": "high"},
    ]
    out = suppress_noise(insights, existing_insight_hashes=lambda o, c: [])
    assert len(out) == 1
