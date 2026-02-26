"""
Campaign performance tool: query marketing_performance_daily, aggregate by campaign.
Returns pandas DataFrame; limit <500 rows.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

MAX_ROWS = 500


def get_campaign_performance(
    client_id: int,
    start_date: date,
    end_date: date,
    *,
    organization_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get campaign-level performance from marketing_performance_daily.
    Aggregates spend, clicks, impressions, conversions, revenue by campaign_id.
    Returns DataFrame with columns: campaign_id, channel, spend, clicks, impressions, conversions, revenue, roas (computed).
    """
    from ..clients.bigquery import load_marketing_performance

    days = max(1, (end_date - start_date).days)
    days = min(days, 365)
    as_of = end_date
    df = load_marketing_performance(
        client_id=client_id,
        as_of_date=as_of,
        days=days,
        organization_id=organization_id,
    )
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "campaign_id", "channel", "spend", "clicks", "impressions",
                "conversions", "revenue", "roas",
            ]
        )

    agg = df.groupby(["campaign_id", "channel"], dropna=False).agg(
        spend=("spend", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    agg["roas"] = agg.apply(
        lambda r: (r["revenue"] / r["spend"]) if r["spend"] and r["spend"] > 0 else 0.0,
        axis=1,
    )
    agg = agg.head(MAX_ROWS)
    return agg
