"""Tests for adstock and saturation."""
import numpy as np

from packages.mmm.src.transforms import adstock_transform, saturation_hill, saturation_log


def test_adstock_half_life():
    x = np.array([1.0, 0.0, 0.0, 0.0])
    out = adstock_transform(x, half_life=1.0)
    assert out[0] == 1.0
    assert out[1] < 1.0
    assert out[3] < out[2]


def test_saturation_log():
    x = np.array([0.0, 1.0, 10.0])
    out = saturation_log(x)
    assert out[0] == 0.0
    assert out[1] == np.log(2)
    assert out[2] == np.log(11)


def test_saturation_hill():
    x = np.array([1.0, 2.0, 10.0])
    out = saturation_hill(x, alpha=1.0, half_saturation=2.0)
    assert 0 <= out[0] <= 1
    assert out[2] > out[1]
