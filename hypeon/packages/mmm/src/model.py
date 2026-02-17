"""
MMM pipeline: StandardScaler, Ridge (default), GridSearchCV for alpha, VIF, elasticities,
bootstrap CI, stability index, confidence score. All confidence/stability clamped [0, 1].
Ridge is the default estimator; optional Lasso. n_boot configurable; capped for large datasets.
"""
from typing import Any, Dict, List, Optional, Union

import numpy as np
from sklearn.linear_model import Ridge, Lasso
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import r2_score, mean_absolute_percentage_error

from packages.governance.src.versions import MMM_VERSION

# Default model version and bootstrap cap
_MODEL_VERSION = MMM_VERSION
_N_BOOT_CAP = 500
_LARGE_N_THRESHOLD = 500


def compute_vif(X: np.ndarray) -> Dict[int, float]:
    """
    Variance Inflation Factor per feature (column index). Singular-safe: on singular matrix
    or zero variance return finite default (1.0) for that column; never raise.
    """
    n_cols = X.shape[1] if X.ndim == 2 else 0
    result: Dict[int, float] = {}
    for j in range(n_cols):
        try:
            other = np.hstack([X[:, i:i + 1] for i in range(n_cols) if i != j])
            if other.size == 0:
                result[j] = 1.0
                continue
            from numpy.linalg import lstsq
            beta, _, _, _ = lstsq(other, X[:, j], rcond=None)
            pred = other @ beta
            ss_res = np.sum((X[:, j] - pred) ** 2)
            ss_tot = np.sum((X[:, j] - np.mean(X[:, j])) ** 2)
            if ss_tot < 1e-20 or ss_res < 1e-20:
                result[j] = 1.0
                continue
            r_sq = 1.0 - ss_res / ss_tot
            vif = 1.0 / (1.0 - r_sq) if r_sq < 1.0 - 1e-10 else 10.0
            result[j] = float(np.clip(vif, 0.0, 1e6))
        except Exception:
            result[j] = 1.0
    return result


def compute_elasticities(
    coefs: np.ndarray,
    mean_spend: Union[np.ndarray, List[float], Dict[str, float]],
    mean_sales: float,
    channel_names: Optional[List[str]] = None,
) -> Dict[str, float]:
    """
    Elasticity = (dY/dX) * (X/Y) at mean. For log saturation: d/dx log(1+x) = 1/(1+x).
    So dY/dX_j = coef_j * (1/(1+mean_spend_j)). Elasticity_j = (dY/dX_j) * (mean_spend_j / mean_sales).
    mean_spend: per-channel mean spend (array in channel order or dict). mean_sales: scalar.
    """
    if mean_sales <= 0 or len(coefs) == 0:
        return {}
    if isinstance(mean_spend, dict):
        channel_names = channel_names or list(mean_spend.keys())
        mean_spend_arr = np.array([mean_spend.get(ch, 0.0) for ch in channel_names], dtype=float)
    else:
        mean_spend_arr = np.asarray(mean_spend, dtype=float)
        channel_names = channel_names or [str(i) for i in range(len(mean_spend_arr))]
    n = min(len(coefs), len(mean_spend_arr), len(channel_names))
    out: Dict[str, float] = {}
    for i in range(n):
        x_bar = max(0.0, mean_spend_arr[i])
        deriv = 1.0 / (1.0 + x_bar) if (1.0 + x_bar) > 1e-10 else 0.0
        dY_dX = coefs[i] * deriv
        elast = dY_dX * (x_bar / mean_sales) if mean_sales else 0.0
        out[channel_names[i]] = float(elast)
    return out


def bootstrap_coefficients(
    X: np.ndarray,
    y: np.ndarray,
    n_boot: int = 500,
    channel_names: Optional[List[str]] = None,
    alpha: float = 0.1,
    seed: Optional[int] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Bootstrap samples, fit Ridge(alpha=alpha), return per-channel/feature CI (low, mean, high).
    n_boot is configurable. If len(y) < 5, reduce n_boot or return empty CIs. For API/runtime cap:
    if n > _LARGE_N_THRESHOLD, reduce n_boot dynamically to avoid blocking.
    """
    import random
    if seed is not None:
        random.seed(seed)
    n = len(y)
    if n < 2 or X.shape[0] != n:
        channels = channel_names or [str(i) for i in range(X.shape[1] if X.ndim == 2 else 0)]
        return {ch: {"low": 0.0, "mean": 0.0, "high": 0.0} for ch in channels}
    if n > _LARGE_N_THRESHOLD:
        n_boot = min(n_boot, max(50, n // 2))
    n_boot = min(n_boot, max(50, n * 2))
    n_cols = X.shape[1]
    channel_names = channel_names or [str(j) for j in range(n_cols)]
    boot_coefs: List[np.ndarray] = []
    for _ in range(n_boot):
        idx = np.random.choice(n, size=n, replace=True)
        X_b = X[idx]
        y_b = y[idx]
        try:
            model = Ridge(alpha=alpha)
            model.fit(X_b, y_b)
            boot_coefs.append(model.coef_.copy())
        except Exception:
            boot_coefs.append(np.zeros(n_cols))
    result: Dict[str, Dict[str, float]] = {}
    for j in range(n_cols):
        ch = channel_names[j] if j < len(channel_names) else str(j)
        vals = [c[j] for c in boot_coefs]
        mean_val = float(np.mean(vals))
        sorted_vals = np.sort(vals)
        low = float(sorted_vals[int(0.025 * len(sorted_vals))])
        high = float(sorted_vals[int(0.975 * len(sorted_vals))])
        result[ch] = {"low": low, "mean": mean_val, "high": high}
    return result


def compute_stability_index(bootstrap_coefs: Dict[str, Dict[str, float]]) -> float:
    """
    Stability from bootstrap coefficient variance: 1 - normalized_cv, clamped [0, 1].
    Deterministic given same bootstrap_coefs.
    """
    if not bootstrap_coefs:
        return 0.0
    means = [b["mean"] for b in bootstrap_coefs.values()]
    if not means or all(m == 0 for m in means):
        return 1.0
    # Use coefficient of variation across channels (std of means / mean of abs(means))
    mean_abs = np.mean(np.abs(means)) or 1.0
    std_means = np.std(means)
    cv = std_means / mean_abs if mean_abs > 1e-10 else 0.0
    stability = 1.0 - min(1.0, cv)
    return float(np.clip(stability, 0.0, 1.0))


def fit_pipeline(
    X: np.ndarray,
    y: np.ndarray,
    channel_names: Optional[List[str]] = None,
    n_boot: int = 500,
    estimator: str = "ridge",
    cv_folds: int = 5,
    alpha_grid: Optional[List[float]] = None,
    model_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: StandardScaler on X, Ridge (default) or Lasso, GridSearchCV for alpha,
    k-fold CV. Returns dict: model_version, r2, adj_r2, mape, vif, elasticities, coefficients,
    bootstrap_ci, stability_index, confidence_score. All scores clamped [0, 1].
    """
    n = len(y)
    n_cols = X.shape[1] if X.ndim == 2 else 0
    channels = channel_names or [str(j) for j in range(n_cols)]
    if alpha_grid is None:
        alpha_grid = [0.01, 0.1, 1.0, 10.0, 100.0]
    out: Dict[str, Any] = {
        "model_version": model_version or _MODEL_VERSION,
        "r2": 0.0,
        "adj_r2": 0.0,
        "mape": 0.0,
        "vif": {},
        "elasticities": {},
        "coefficients": {},
        "bootstrap_ci": {},
        "stability_index": 0.0,
        "confidence_score": 0.0,
    }
    if X.size == 0 or n < 2:
        return out
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    if estimator == "lasso":
        est = Lasso()
    else:
        est = Ridge()
    param_grid = {"alpha": alpha_grid}
    try:
        gs = GridSearchCV(est, param_grid, cv=min(cv_folds, n), scoring="r2")
        gs.fit(X_scaled, y)
        best = gs.best_estimator_
        cv_scores = gs.cv_results_.get("mean_test_score", [])
        cv_mean_r2 = float(np.mean(cv_scores)) if cv_scores else 0.0
        cv_error = 1.0 - max(0.0, cv_mean_r2)
    except Exception:
        best = Ridge(alpha=1.0).fit(X_scaled, y)
        cv_error = 0.5
    y_pred = best.predict(X_scaled)
    r2 = float(r2_score(y, y_pred))
    n_params = X_scaled.shape[1]
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / max(1, n - n_params - 1) if n > n_params + 1 else r2
    adj_r2 = max(0.0, min(1.0, adj_r2))
    try:
        mape = float(mean_absolute_percentage_error(y, np.maximum(y_pred, 1e-10)))
    except Exception:
        mape = 0.0
    coefs = best.coef_
    out["r2"] = max(0.0, min(1.0, r2))
    out["adj_r2"] = adj_r2
    out["mape"] = mape
    out["coefficients"] = {channels[j]: float(coefs[j]) for j in range(min(len(coefs), len(channels)))}
    out["vif"] = {str(j): v for j, v in compute_vif(X_scaled).items()}
    mean_spend = np.mean(X, axis=0)
    mean_sales = float(np.mean(y)) if len(y) else 0.0
    out["elasticities"] = compute_elasticities(coefs, mean_spend, mean_sales, channel_names=channels)
    out["bootstrap_ci"] = bootstrap_coefficients(
        X_scaled, y, n_boot=n_boot, channel_names=channels, alpha=getattr(best, "alpha", 1.0)
    )
    out["stability_index"] = compute_stability_index(out["bootstrap_ci"])
    avg_vif = np.mean(list(out["vif"].values())) if out["vif"] else 0.0
    avg_vif_norm = min(1.0, avg_vif / 10.0)
    confidence = (
        out["r2"] * (1.0 - avg_vif_norm) * out["stability_index"] * (1.0 - cv_error)
    )
    out["confidence_score"] = float(np.clip(confidence, 0.0, 1.0))
    return out
