"""Tests for decision simulator."""
from packages.mmm.src.simulator import projected_revenue_delta


def test_projected_revenue_delta_positive():
    current = {"meta": 100.0, "google": 50.0}
    changes = {"meta": 0.2}
    coefs = {"meta": 1.0, "google": 0.5}
    delta = projected_revenue_delta(current, changes, coefs)
    assert delta >= 0


def test_projected_revenue_delta_zero_when_no_change():
    current = {"meta": 100.0, "google": 50.0}
    changes = {}
    coefs = {"meta": 1.0, "google": 0.5}
    delta = projected_revenue_delta(current, changes, coefs)
    assert abs(delta) < 1e-6
