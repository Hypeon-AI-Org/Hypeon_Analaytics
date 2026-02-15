"""
Decision simulator: given spend changes per channel, return projected revenue delta
using the MMM response curve (adstock + saturation).
"""
from typing import Dict

from packages.mmm.src.optimizer import predicted_revenue

DEFAULT_ADSTOCK_HALF_LIFE = 7.0


def projected_revenue_delta(
    current_spend: Dict[str, float],
    spend_changes: Dict[str, float],
    coefficients: Dict[str, float],
    half_life: float = DEFAULT_ADSTOCK_HALF_LIFE,
) -> float:
    """
    spend_changes: fractional change per channel, e.g. {"meta": 0.2, "google": -0.1} => +20% meta, -10% google.
    Returns predicted_revenue(new_spend) - predicted_revenue(current_spend).
    """
    new_spend = {
        ch: current_spend.get(ch, 0.0) * (1.0 + spend_changes.get(ch, 0.0))
        for ch in set(list(current_spend.keys()) + list(spend_changes.keys()))
    }
    rev_current = predicted_revenue(current_spend, coefficients, half_life)
    rev_new = predicted_revenue(new_spend, coefficients, half_life)
    return rev_new - rev_current
