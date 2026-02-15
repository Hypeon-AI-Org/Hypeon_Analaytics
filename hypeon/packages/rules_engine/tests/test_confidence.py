"""Tests for confidence scoring."""
from datetime import date, timedelta

from packages.rules_engine.src.confidence import confidence_score


def test_confidence_r2():
    assert 0 <= confidence_score(r2=0.5) <= 1
    assert confidence_score(r2=1.0) >= confidence_score(r2=0.0)


def test_confidence_sample_size():
    assert confidence_score(sample_size=100) >= 0
    assert confidence_score(sample_size=1000) >= confidence_score(sample_size=10)


def test_confidence_bounded():
    assert 0 <= confidence_score(r2=2.0, sample_size=1_000_000) <= 1.0
