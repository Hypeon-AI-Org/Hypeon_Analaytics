"""Test simulation service."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.simulation import simulate_budget_shift


def test_simulate_returns_structure():
    out = simulate_budget_shift(
        client_id=1,
        date_str="2025-02-22",
        from_campaign="c1",
        to_campaign="c2",
        amount=100.0,
    )
    assert "low" in out and "median" in out and "high" in out
    assert "expected_delta" in out
    assert "confidence" in out
    assert out["confidence"] >= 0 and out["confidence"] <= 1
