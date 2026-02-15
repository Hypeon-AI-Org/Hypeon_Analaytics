"""Tests for Markov removal-effect."""
from packages.attribution.src.markov import build_transition_matrix, markov_credits, removal_effect


def test_build_transition_matrix():
    sequences = [["meta", "google"], ["meta", "meta", "google"]]
    channels = ["meta", "google"]
    P = build_transition_matrix(sequences, channels)
    assert P.shape == (3, 3)
    assert P.sum(axis=1).max() <= 1.01


def test_removal_effect():
    import numpy as np
    P = np.array([
        [0, 0.5, 0.5],
        [0, 0, 1],
        [0, 0, 1],
    ])
    e = removal_effect(P, 0, 2)
    assert 0 <= e <= 1


def test_markov_credits_insufficient_data_returns_none():
    out = markov_credits([["meta"]], ["meta", "google"], min_sequences=10)
    assert out is None


def test_markov_credits_returns_weights():
    sequences = [["meta", "google"], ["google", "meta"]] * 6
    out = markov_credits(sequences, ["meta", "google"], min_sequences=5)
    assert out is not None
    assert abs(sum(out.values()) - 1.0) < 1e-6
