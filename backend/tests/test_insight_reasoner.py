"""Tests for insight_reasoner: signals -> reasoned insight."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from backend.app.insight_reasoner import reason_insights, _infer_root_cause_and_impact, _recommendation_from_signals


def test_infer_root_cause_roas_drop():
    cause, impact, conf = _infer_root_cause_and_impact(["roas_drop"])
    assert "ROAS" in cause or "decline" in cause.lower()
    assert impact in ("HIGH", "MEDIUM", "LOW")
    assert 0 <= conf <= 1


def test_infer_root_cause_combined():
    cause, impact, conf = _infer_root_cause_and_impact(["roas_drop", "conversion_drop"])
    assert "quality" in cause.lower() or "degradation" in cause.lower()
    assert impact == "HIGH"


def test_recommendation_high_impact():
    rec = _recommendation_from_signals(["roas_drop"], "HIGH")
    assert "spend" in rec.lower() or "budget" in rec.lower()


def test_reason_insights_aggregates_by_entity():
    outputs = [
        {"entity_id": "c1_a1", "client_id": 1, "organization_id": "org1", "signals": ["roas_drop"]},
        {"entity_id": "c1_a1", "client_id": 1, "organization_id": "org1", "signals": ["conversion_drop"]},
    ]
    out = reason_insights(outputs, organization_id="org1")
    assert len(out) == 1
    assert "roas_drop" in out[0].get("signals", []) and "conversion_drop" in out[0].get("signals", [])
    assert out[0].get("root_cause") and out[0].get("impact_level")
    assert out[0].get("recommendation")
    assert out[0].get("insight_id")
