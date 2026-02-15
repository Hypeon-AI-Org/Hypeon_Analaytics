"""MMM regression: OLS or Ridge on adstocked + saturated features."""
from typing import Dict, Optional, Tuple

import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import r2_score


def fit_mmm(
    X: np.ndarray,
    y: np.ndarray,
    ridge_alpha: float = 0.0,
) -> Tuple[np.ndarray, float, object]:
    """
    Fit target y vs features X. If ridge_alpha > 0 use Ridge else OLS.
    Returns (coefficients, R², fitted model).
    """
    if ridge_alpha > 0:
        model = Ridge(alpha=ridge_alpha)
    else:
        model = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)
    r2 = r2_score(y, y_pred)
    return model.coef_, float(r2), model


def marginal_roas(
    coef: np.ndarray,
    spend: np.ndarray,
    delta: float = 0.01,
    saturation_curve: Optional[np.ndarray] = None,
) -> float:
    """
    Approximate marginal ROAS at current spend: d(revenue)/d(spend) ~ coefficient * derivative of saturation.
    If saturation_curve is None, assume linear (derivative 1). Else use finite difference.
    """
    if saturation_curve is None or len(spend) == 0:
        return float(coef[0]) if len(coef) else 0.0
    spend_plus = spend + delta
    sat_plus = np.log1p(np.maximum(spend_plus, 0))
    sat = np.log1p(np.maximum(spend, 0))
    dr_dspend = (sat_plus - sat) / delta
    return float(coef[0] * dr_dspend.mean()) if len(coef) else 0.0
