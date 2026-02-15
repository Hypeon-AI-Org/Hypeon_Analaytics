"""Tests for budget optimizer."""
from packages.mmm.src.optimizer import (
    allocate_budget_greedy,
    marginal_roas_at_spend,
    predicted_revenue,
)


def test_predicted_revenue():
    coefs = {"meta": 1.0, "google": 0.5}
    spend = {"meta": 100.0, "google": 50.0}
    rev = predicted_revenue(spend, coefs)
    assert rev >= 0


def test_marginal_roas_decreases_with_spend():
    coefs = {"meta": 1.0}
    low = marginal_roas_at_spend({"meta": 10.0}, coefs)
    high = marginal_roas_at_spend({"meta": 1000.0}, coefs)
    assert low["meta"] >= high["meta"]


def test_allocate_budget_greedy():
    coefs = {"meta": 2.0, "google": 1.0}
    alloc = allocate_budget_greedy(100.0, coefs, current_spend=None, step=10.0)
    assert sum(alloc.values()) <= 100.0 + 1e-6
    assert set(alloc.keys()) == {"meta", "google"}
