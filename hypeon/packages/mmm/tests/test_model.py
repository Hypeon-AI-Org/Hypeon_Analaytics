"""Tests for MMM model pipeline: Ridge, VIF, bootstrap, stability, confidence."""
import numpy as np

from packages.mmm.src.model import (
    compute_vif,
    compute_elasticities,
    bootstrap_coefficients,
    compute_stability_index,
    fit_pipeline,
)


def test_compute_vif_singular_safe():
    X = np.ones((10, 2))
    out = compute_vif(X)
    assert 0 in out and 1 in out
    assert out[0] >= 0 and out[1] >= 0


def test_compute_vif_normal():
    np.random.seed(42)
    X = np.random.randn(50, 3)
    out = compute_vif(X)
    assert len(out) == 3


def test_compute_elasticities():
    coefs = np.array([1.0, 2.0])
    mean_spend = np.array([10.0, 20.0])
    mean_sales = 100.0
    out = compute_elasticities(coefs, mean_spend, mean_sales, channel_names=["a", "b"])
    assert "a" in out and "b" in out


def test_bootstrap_coefficients_small_n():
    X = np.random.randn(8, 2)
    y = np.random.randn(8)
    out = bootstrap_coefficients(X, y, n_boot=30, channel_names=["x", "y"])
    assert "x" in out and "y" in out
    assert "mean" in out["x"] and "low" in out["x"] and "high" in out["x"]


def test_compute_stability_index():
    bootstrap_coefs = {"a": {"mean": 0.5}, "b": {"mean": 0.5}}
    s = compute_stability_index(bootstrap_coefs)
    assert 0 <= s <= 1


def test_compute_stability_index_clamp():
    bootstrap_coefs = {"a": {"mean": 1.0}, "b": {"mean": -1.0}}
    s = compute_stability_index(bootstrap_coefs)
    assert 0 <= s <= 1


def test_fit_pipeline_ridge():
    X = np.random.randn(40, 2)
    y = 2.0 + X[:, 0] * 0.5 + X[:, 1] * 0.3 + np.random.randn(40) * 0.1
    out = fit_pipeline(X, y, channel_names=["c1", "c2"], n_boot=50)
    assert "r2" in out and "coefficients" in out
    assert 0 <= out["r2"] <= 1.01
    assert 0 <= out["confidence_score"] <= 1
    assert 0 <= out["stability_index"] <= 1
    assert "c1" in out["coefficients"] and "c2" in out["coefficients"]


def test_fit_pipeline_confidence_clamp():
    X = np.random.randn(15, 2)
    y = np.random.randn(15)
    out = fit_pipeline(X, y, n_boot=30)
    assert 0 <= out["confidence_score"] <= 1
