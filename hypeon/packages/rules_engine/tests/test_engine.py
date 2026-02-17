"""Tests for decision engine: confidence formula, output shape."""
from datetime import datetime
from unittest.mock import MagicMock

from packages.rules_engine.src.engine import (
    decision_confidence,
    enrich_decision_row,
    Rule,
)


def test_decision_confidence_formula():
    c = decision_confidence(0.8, 0.9, 0.7)
    assert abs(c - (0.8 * 0.9 * 0.7)) < 1e-6
    assert 0 <= c <= 1


def test_decision_confidence_clamp():
    c = decision_confidence(1.5, 1.0, 1.0)
    assert c == 1.0
    c = decision_confidence(0.0, 0.5, 0.5)
    assert c == 0.0


def test_enrich_decision_row_shape():
    row = MagicMock(spec=None)
    row.decision_id = "dec-1"
    row.entity_type = "channel"
    row.entity_id = "meta"
    row.decision_type = "scale_up"
    row.projected_impact = 0.1
    row.confidence_score = 0.7
    row.explanation_text = "ROAS high"
    row.status = "pending"
    row.created_at = datetime(2025, 1, 1)
    out = enrich_decision_row(row, run_id="run-1", mta_version="mta_v1.1", mmm_version="mmm_v2.0")
    assert out["decision_id"] == "dec-1"
    assert out["channel"] == "meta"
    assert out["recommended_action"] == "Scale Up"
    assert out["budget_change_pct"] == 10.0
    assert "reasoning" in out and "mta_support" in out["reasoning"]
    assert "risk_flags" in out
    assert "confidence_score" in out
    assert out["model_versions"]["mta_version"] == "mta_v1.1"
    assert out["run_id"] == "run-1"
