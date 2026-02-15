"""Tests for MMM regression."""
import numpy as np

from packages.mmm.src.regression import fit_mmm


def test_fit_mmm_ols():
    X = np.array([[1, 0], [2, 1], [3, 2]], dtype=float)
    y = np.array([1.0, 2.0, 3.0])
    coef, r2, _ = fit_mmm(X, y, ridge_alpha=0.0)
    assert len(coef) == 2
    assert 0 <= r2 <= 1.01
