import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.impact_estimator import estimate_impact, get_severity


def test_estimate_waste():
    out = estimate_impact("waste_zero_revenue", {"spend": 100, "revenue": 0})
    assert out["potential_savings"] == 100
    assert out["risk_level"] == "high"


def test_estimate_scale_opportunity():
    out = estimate_impact("scale_opportunity", {"spend": 50, "revenue": 100, "roas": 2, "roas_28d_avg": 1.5})
    assert "potential_revenue_gain" in out
    assert out["risk_level"] == "low"
