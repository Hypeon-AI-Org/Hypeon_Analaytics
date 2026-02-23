"""
Estimate potential_savings, potential_revenue_gain, risk_level from historical averages.
Example: ROAS_drop × spend_last_7d for revenue impact.
"""
from __future__ import annotations

from typing import Any, Optional


# Severity mapping for insight types
SEVERITY_MAP = {
    "waste_zero_revenue": "high",
    "roas_decline": "high",
    "funnel_leak": "medium",
    "scale_opportunity": "low",
    "anomaly": "medium",
}


def estimate_impact(
    insight_type: str,
    row: dict[str, Any],
    *,
    spend_7d: Optional[float] = None,
    revenue_7d: Optional[float] = None,
) -> dict[str, Any]:
    """
    Return potential_savings, potential_revenue_gain, risk_level.
    Uses row (aggregated metrics) and optional 7d totals.
    """
    spend = float(row.get("spend") or 0)
    revenue = float(row.get("revenue") or 0)
    roas = float(row.get("roas") or 0)
    roas_28d_avg = float(row.get("roas_28d_avg") or 0)
    spend_7d = spend_7d if spend_7d is not None else spend
    revenue_7d = revenue_7d if revenue_7d is not None else revenue

    potential_savings = 0.0
    potential_revenue_gain = 0.0
    risk_level = "low"

    if insight_type == "waste_zero_revenue":
        potential_savings = spend_7d
        risk_level = "high"
    elif insight_type == "roas_decline":
        if roas_28d_avg > 0 and spend_7d > 0:
            potential_revenue_gain = (roas_28d_avg - roas) * spend_7d
        potential_savings = spend_7d * 0.2
        risk_level = "high"
    elif insight_type == "scale_opportunity":
        if roas > 0 and spend_7d > 0:
            potential_revenue_gain = (roas - roas_28d_avg) * spend_7d * 0.5
        risk_level = "low"
    elif insight_type == "funnel_leak":
        potential_revenue_gain = revenue_7d * 0.1
        risk_level = "medium"
    elif insight_type == "anomaly":
        risk_level = "medium"

    return {
        "potential_savings": round(potential_savings, 2),
        "potential_revenue_gain": round(potential_revenue_gain, 2),
        "risk_level": risk_level,
    }


def get_severity(insight_type: str) -> str:
    return SEVERITY_MAP.get(insight_type, "medium")
