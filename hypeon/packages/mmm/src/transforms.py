"""Adstock (half-life) and saturation (Hill / log) transforms for MMM."""
import numpy as np


def adstock_transform(x: np.ndarray, half_life: float) -> np.ndarray:
    """
    Geometric adstock with decay. half_life in periods; decay = 0.5^(1/half_life).
    """
    if half_life <= 0 or len(x) == 0:
        return x.copy()
    decay = 0.5 ** (1.0 / half_life)
    out = np.zeros_like(x, dtype=float)
    out[0] = x[0]
    for t in range(1, len(x)):
        out[t] = x[t] + decay * out[t - 1]
    return out


def saturation_hill(x: np.ndarray, alpha: float, half_saturation: float) -> np.ndarray:
    """Hill saturation: x^alpha / (x^alpha + half_saturation^alpha)."""
    x = np.asarray(x, dtype=float)
    x = np.maximum(x, 1e-10)
    return (x ** alpha) / (x ** alpha + half_saturation ** alpha)


def saturation_log(x: np.ndarray) -> np.ndarray:
    """Log transform: log(1 + x)."""
    x = np.asarray(x, dtype=float)
    return np.log1p(np.maximum(x, 0))
