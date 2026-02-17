"""
Budget optimizer: reallocate total spend S across channels to maximize predicted incremental revenue.
Uses marginal ROAS (derivative of MMM response) sorted descending; greedy allocation respecting saturation.
"""
from typing import Dict, List, Optional

import numpy as np

from packages.mmm.src.transforms import adstock_transform, saturation_log


DEFAULT_ADSTOCK_HALF_LIFE = 7.0
_DELTA = 1.0  # finite difference for marginal ROAS


def _response_single_channel(spend: float, half_life: float = DEFAULT_ADSTOCK_HALF_LIFE) -> float:
    """MMM response for one channel: saturation_log(adstock(spend)). Use 30-day constant spend for adstock."""
    if spend <= 0:
        return 0.0
    n = 30
    x = np.full(n, spend, dtype=float)
    adstocked = adstock_transform(x, half_life)
    return float(saturation_log(adstocked[-1:])[0])


def predicted_revenue(
    spend_by_channel: Dict[str, float],
    coefficients: Dict[str, float],
    half_life: float = DEFAULT_ADSTOCK_HALF_LIFE,
) -> float:
    """Total predicted revenue = sum_j coef_j * response(spend_j)."""
    total = 0.0
    for ch, spend in spend_by_channel.items():
        coef = coefficients.get(ch, 0.0)
        total += coef * _response_single_channel(spend, half_life)
    return total


def marginal_roas_at_spend(
    spend_by_channel: Dict[str, float],
    coefficients: Dict[str, float],
    half_life: float = DEFAULT_ADSTOCK_HALF_LIFE,
    delta: float = _DELTA,
) -> Dict[str, float]:
    """Marginal ROAS per channel at current spend (finite difference)."""
    out = {}
    for ch, spend in spend_by_channel.items():
        coef = coefficients.get(ch, 0.0)
        if coef <= 0:
            out[ch] = 0.0
            continue
        r0 = _response_single_channel(spend, half_life)
        r1 = _response_single_channel(spend + delta, half_life)
        out[ch] = coef * (r1 - r0) / delta if delta else 0.0
    return out


STABILITY_THRESHOLD_DEFAULT = 0.3


def allocate_budget_greedy(
    total_budget: float,
    coefficients: Dict[str, float],
    current_spend: Optional[Dict[str, float]] = None,
    half_life: float = DEFAULT_ADSTOCK_HALF_LIFE,
    step: float = 10.0,
    channel_min_pct: Optional[Dict[str, float]] = None,
    channel_max_pct: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Greedy allocation: repeatedly add `step` to the channel with highest marginal ROAS
    until total spend reaches total_budget. Respects saturation (marginal ROAS decreases).
    If current_spend is provided, start from it; else start from 0 per channel.
    Enforces non-negative spend. Optional channel_min_pct/channel_max_pct (0..1) cap share of total_budget.
    """
    channels = list(coefficients.keys())
    if not channels:
        return {}
    spend = dict(current_spend) if current_spend else {ch: 0.0 for ch in channels}
    for ch in spend:
        spend[ch] = max(0.0, spend[ch])
    total_current = sum(spend.values())
    if total_current >= total_budget and total_current > 0:
        scale = total_budget / total_current
        return {ch: spend[ch] * scale for ch in spend}
    remaining = total_budget - total_current
    while remaining > 1e-6 and step > 0:
        add = min(step, remaining)
        mroas = marginal_roas_at_spend(spend, coefficients, half_life, delta=add)
        best_ch = max(channels, key=lambda c: mroas.get(c, 0.0))
        if mroas.get(best_ch, 0.0) <= 0:
            break
        spend[best_ch] = max(0.0, spend.get(best_ch, 0.0) + add)
        remaining -= add
    if channel_min_pct or channel_max_pct:
        total = sum(spend.values()) or 1.0
        for ch in channels:
            pct = spend[ch] / total
            if channel_min_pct and ch in channel_min_pct:
                spend[ch] = max(spend[ch], total_budget * channel_min_pct[ch])
            if channel_max_pct and ch in channel_max_pct:
                spend[ch] = min(spend[ch], total_budget * channel_max_pct[ch])
        scale = total_budget / (sum(spend.values()) or 1.0)
        spend = {ch: spend[ch] * scale for ch in spend}
    return spend


def allocate_budget_greedy_with_guard(
    total_budget: float,
    coefficients: Dict[str, float],
    current_spend: Dict[str, float],
    stability_index: Optional[float] = None,
    stability_threshold: float = STABILITY_THRESHOLD_DEFAULT,
    half_life: float = DEFAULT_ADSTOCK_HALF_LIFE,
) -> Dict:
    """
    Run optimizer only if stability_index is None or >= stability_threshold. Otherwise return
    {"stable": False, "message": "Model not stable", "recommended_allocation": current_spend}.
    """
    if stability_index is not None and stability_index < stability_threshold:
        return {
            "stable": False,
            "message": "Model not stable",
            "recommended_allocation": dict(current_spend),
        }
    recommended = allocate_budget_greedy(
        total_budget, coefficients, current_spend=current_spend, half_life=half_life,
    )
    return {"stable": True, "recommended_allocation": recommended}


def recommend_reallocation(
    total_budget: float,
    coefficients: Dict[str, float],
    current_spend: Dict[str, float],
    half_life: float = DEFAULT_ADSTOCK_HALF_LIFE,
) -> Dict[str, float]:
    """
    Recommend spend per channel to maximize predicted revenue given total_budget.
    Uses greedy allocation from current_spend toward optimal (marginal ROAS balanced).
    """
    return allocate_budget_greedy(
        total_budget,
        coefficients,
        current_spend=current_spend,
        half_life=half_life,
        step=max(1.0, total_budget * 0.01),
    )
