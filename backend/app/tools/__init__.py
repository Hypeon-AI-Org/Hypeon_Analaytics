# Data analysis tools: query marketing_performance_daily only; return DataFrames (limit 500 rows).

from .campaign_performance import get_campaign_performance
from .channel_breakdown import get_channel_breakdown
from .period_comparison import compare_periods

__all__ = [
    "get_campaign_performance",
    "get_channel_breakdown",
    "compare_periods",
]
