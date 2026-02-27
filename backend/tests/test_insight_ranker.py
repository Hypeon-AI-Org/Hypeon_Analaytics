import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime, timezone, timedelta
from backend.app.insight_ranker import compute_priority_score, rank_insights, top_per_client, get_severity


def test_severity():
    assert get_severity("waste_zero_revenue") == "high"
    assert get_severity("scale_opportunity") == "medium"


def test_compute_priority_score():
    insight = {"confidence": 0.8, "expected_impact_value": 0.5, "insight_type": "roas_decline", "created_at": datetime.now(timezone.utc).isoformat()}
    s = compute_priority_score(insight)
    assert s > 0


def test_rank_insights():
    insights = [
        {"client_id": 1, "organization_id": "org1", "insight_type": "waste_zero_revenue", "confidence": 0.9, "expected_impact": {"estimate": 0.2}, "created_at": None},
        {"client_id": 1, "organization_id": "org1", "insight_type": "scale_opportunity", "confidence": 0.5, "expected_impact": {"estimate": 0.1}, "created_at": None},
    ]
    ranked = rank_insights(insights)
    assert len(ranked) == 2
    assert ranked[0].get("rank") == 1
    assert ranked[0].get("priority_score") is not None
    assert ranked[0].get("severity") == "high"


def test_top_per_client():
    insights = [
        {"client_id": 1, "organization_id": "org1", "insight_type": "waste_zero_revenue", "confidence": 0.9, "expected_impact_value": 0.3, "created_at": None},
        {"client_id": 1, "organization_id": "org1", "insight_type": "roas_decline", "confidence": 0.8, "expected_impact_value": 0.2, "created_at": None},
        {"client_id": 1, "organization_id": "org1", "insight_type": "scale_opportunity", "confidence": 0.5, "expected_impact_value": 0.1, "created_at": None},
    ]
    top = top_per_client(rank_insights(insights), top_n=2)
    assert len(top) == 2
