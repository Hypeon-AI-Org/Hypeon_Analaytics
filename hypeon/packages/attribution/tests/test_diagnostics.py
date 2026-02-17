"""Tests for attribution diagnostics: path frequency, removal effect, bootstrap, confidence."""
import math

from packages.attribution.src.diagnostics import (
    compute_path_frequency,
    compute_removal_effect_table,
    bootstrap_channel_contributions,
    compute_lag_distribution,
    run_diagnostics,
)


def test_compute_path_frequency():
    sequences = [["meta", "google"], ["meta", "google"], ["google"]]
    out = compute_path_frequency(sequences)
    assert out["meta>google"] == 2
    assert out["google"] == 1
    assert len(out) == 2


def test_compute_path_frequency_empty():
    out = compute_path_frequency([])
    assert out == {}


def test_compute_removal_effect_table():
    channels = ["meta", "google"]
    sequences = [["meta", "google"]] * 15
    out = compute_removal_effect_table(sequences, channels)
    assert set(out.keys()) == {"meta", "google"}
    assert all(0 <= v <= 1 for v in out.values())
    assert abs(sum(out.values()) - 1.0) < 0.01


def test_bootstrap_channel_contributions_small_n():
    channels = ["meta", "google"]
    sequences = [["meta", "google"], ["google", "meta"]] * 3
    out = bootstrap_channel_contributions(sequences, channels, n_boot=50, min_sequences=2)
    for ch in channels:
        assert ch in out
        assert "low" in out[ch] and "mean" in out[ch] and "high" in out[ch]
        assert 0 <= out[ch]["mean"] <= 1
        assert out[ch]["low"] <= out[ch]["mean"] <= out[ch]["high"]


def test_bootstrap_does_not_crash_tiny():
    out = bootstrap_channel_contributions([], ["meta", "google"], n_boot=10)
    assert out["meta"]["mean"] == 0.0 and out["google"]["mean"] == 0.0


def test_confidence_clamp():
    result = run_diagnostics(
        [["meta"], ["google"]] * 5,
        channels=["meta", "google"],
        conversion_density_score=2.0,
    )
    assert 0 <= result["confidence_score"] <= 1


def test_compute_lag_distribution():
    sequences = [["meta", "google", "meta"], ["google"]]
    out = compute_lag_distribution(sequences)
    assert "position_counts" in out
    assert "num_paths" in out
    assert out["num_paths"] == 2


def test_run_diagnostics_returns_all_keys():
    sequences = [["meta", "google"]] * 20
    out = run_diagnostics(sequences, channels=["meta", "google"])
    assert "path_frequency" in out
    assert "removal_effect" in out
    assert "bootstrap_ci" in out
    assert "lag_distribution" in out
    assert "window_sensitivity" in out
    assert "confidence_score" in out
    assert 0 <= out["confidence_score"] <= 1
