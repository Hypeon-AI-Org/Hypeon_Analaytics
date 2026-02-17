"""Tests for MTA vs MMM reconciliation: alignment score, conflict_flag at 30%."""
from packages.product_engine.src.reconciliation import compute_reconciliation, CONFLICT_THRESHOLD


def test_alignment_score_perfect():
    mta = {"meta": 0.5, "google": 0.5}
    mmm = {"meta": 0.5, "google": 0.5}
    out = compute_reconciliation(mta, mmm)
    assert out["overall_alignment_score"] == 1.0
    assert out["channel_alignment"]["meta"]["delta_pct"] == 0.0
    assert out["channel_alignment"]["meta"]["conflict_flag"] is False


def test_conflict_flag_at_30():
    mta = {"meta": 0.4, "google": 0.6}
    mmm = {"meta": 0.0, "google": 1.0}
    out = compute_reconciliation(mta, mmm)
    assert out["channel_alignment"]["meta"]["delta_pct"] == 0.4
    assert out["channel_alignment"]["meta"]["conflict_flag"] is True
    assert out["channel_alignment"]["google"]["delta_pct"] == 0.4
    assert out["channel_alignment"]["google"]["conflict_flag"] is True


def test_alignment_score_clamped():
    mta = {"meta": 1.0, "google": 0.0}
    mmm = {"meta": 0.0, "google": 1.0}
    out = compute_reconciliation(mta, mmm)
    assert 0 <= out["overall_alignment_score"] <= 1
    assert out["overall_alignment_score"] == 0.0


def test_alignment_confidence_clamped():
    out = compute_reconciliation({"a": 0.5}, {"a": 0.5}, alignment_confidence=1.5)
    assert out["alignment_confidence"] == 1.0
