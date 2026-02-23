"""Unit tests for rules_engine."""
from datetime import date

import pandas as pd
import pytest

# Import from backend.app (assume backend is on path or run from repo root)
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.rules_engine import (
    _insight_id,
    _evaluate_condition,
    _format_template,
    _row_to_insight,
    generate_insights,
    _aggregate_28d,
)


def test_insight_id_deterministic():
    a = _insight_id("r1", "campaign", "c1", "2025-02-22")
    b = _insight_id("r1", "campaign", "c1", "2025-02-22")
    assert a == b
    c = _insight_id("r1", "campaign", "c2", "2025-02-22")
    assert a != c


def test_format_template():
    assert _format_template("Hello {x}", x="world") == "Hello world"
    assert _format_template("{a} {b}", a=1, b=2) == "1 2"


def test_evaluate_condition():
    # revenue eq 0, min_spend 1
    assert _evaluate_condition({"revenue": 0, "spend": 10}, {"metric": "revenue", "op": "eq", "value": 0, "min_spend": 1}) is True
    assert _evaluate_condition({"revenue": 0, "spend": 0}, {"metric": "revenue", "op": "eq", "value": 0, "min_spend": 1}) is False
    # roas_pct_delta_28d lt -0.2
    assert _evaluate_condition({"roas_pct_delta_28d": -0.3, "spend": 20}, {"metric": "roas_pct_delta_28d", "op": "lt", "value": -0.2, "min_spend": 10}) is True
    assert _evaluate_condition({"roas_pct_delta_28d": -0.1, "spend": 20}, {"metric": "roas_pct_delta_28d", "op": "lt", "value": -0.2, "min_spend": 10}) is False


def test_aggregate_28d():
    df = pd.DataFrame({
        "client_id": [1, 1],
        "channel": ["google_ads", "google_ads"],
        "campaign_id": ["c1", "c1"],
        "ad_group_id": ["a1", "a1"],
        "device": ["MOBILE", "DESKTOP"],
        "spend": [10.0, 20.0],
        "revenue": [0, 50.0],
        "clicks": [5, 10],
        "impressions": [100, 200],
        "sessions": [0, 0],
        "conversions": [0, 2],
    })
    agg = _aggregate_28d(df)
    assert len(agg) == 2
    assert "roas" in agg.columns
    assert agg["spend"].sum() == 30.0


def test_row_to_insight():
    rule = {
        "id": "waste_zero_revenue",
        "insight_type": "waste_zero_revenue",
        "summary_template": "Campaign {entity_id} has spend but zero revenue.",
        "explanation_template": "Spend = {spend}, revenue = 0.",
        "recommendation_template": "Pause {entity_id}.",
    }
    row = {"spend": 100, "revenue": 0, "roas": 0, "sessions": 0, "conversions": 0, "conversion_rate": 0,
           "roas_28d_avg": 0, "revenue_28d_avg": 0, "roas_pct_delta_28d": None}
    out = _row_to_insight(rule, "campaign", "c1_a1", 1, "2025-02-22", row, "default", None)
    assert out["insight_id"] == _insight_id("waste_zero_revenue", "campaign", "c1_a1", "2025-02-22", "default")
    assert out["client_id"] == 1
    assert out["status"] == "new"
    assert "100" in out["explanation"]
    assert out["evidence"] is not None


def test_generate_insights_mock_data():
    """Generate insights from mock DataFrame; do not write to BQ."""
    def mock_load(client_id: int, as_of_date: date, days: int = 28):
        return pd.DataFrame({
            "client_id": [1],
            "channel": ["google_ads"],
            "campaign_id": ["c1"],
            "ad_group_id": ["a1"],
            "device": ["MOBILE"],
            "spend": [50.0],
            "revenue": [0.0],
            "clicks": [10],
            "impressions": [200],
            "sessions": [0],
            "conversions": [0],
            "roas": [0.0],
            "roas_28d_avg": [0.0],
            "revenue_28d_avg": [0.0],
            "roas_pct_delta_28d": [0.0],
        })

    insights = generate_insights(1, date(2025, 2, 22), load_data=mock_load, write=False)
    # waste_zero_revenue: revenue=0, spend>=1 -> should fire
    assert len(insights) >= 1
    assert insights[0]["insight_type"] == "waste_zero_revenue"
    assert insights[0]["client_id"] == 1
    # Idempotent id
    insights2 = generate_insights(1, date(2025, 2, 22), load_data=mock_load, write=False)
    assert insights[0]["insight_id"] == insights2[0]["insight_id"]
