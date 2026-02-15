"""Confidence score (0-1) from model R², sample size, and recency decay."""
from datetime import date, timedelta
from typing import Optional


def confidence_score(
    r2: Optional[float] = None,
    sample_size: int = 0,
    reference_date: Optional[date] = None,
    decay_days: int = 90,
) -> float:
    """
    Combine R² (model fit), sample size, and recency into a 0-1 confidence score.
    - R² contributes up to 0.5 (cap at 1.0)
    - Sample size: log scale, e.g. 100+ -> 0.3, 1000+ -> 0.5
    - Recency: exponential decay from reference_date; older data reduces score
    """
    score = 0.0
    if r2 is not None and r2 >= 0:
        score += 0.5 * min(1.0, r2)
    if sample_size > 0:
        import math
        score += 0.3 * min(1.0, math.log1p(sample_size) / 7)
    if reference_date is not None:
        today = date.today()
        days_ago = (today - reference_date).days
        decay = 0.2 * (0.5 ** (days_ago / max(1, decay_days)))
        score += decay
    return min(1.0, max(0.0, score))
