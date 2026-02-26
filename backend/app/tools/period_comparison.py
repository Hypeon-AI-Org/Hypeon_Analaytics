"""
Period comparison tool: query marketing_performance_daily for two windows (e.g. this week vs last week).
Returns pandas DataFrame with period label and aggregates; limit <500 rows.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

MAX_ROWS = 500


def compare_periods(
    client_id: int,
    start_date: date,
    end_date: date,
    *,
    period_a_label: str = "current",
    period_b_label: str = "previous",
    period_a_days: Optional[int] = None,
    period_b_days: Optional[int] = None,
    organization_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Compare two periods from marketing_performance_daily.
    If period_a_days/period_b_days not set: period A = (start_date, end_date), period B = same length ending day before start_date.
    Returns DataFrame with one row per period: period_label, spend, revenue, conversions, roas, and daily-level rows (date, period_label, ...) up to MAX_ROWS.
    """
    from ..clients.bigquery import load_marketing_performance

    total_days = max(1, (end_date - start_date).days)
    total_days = min(total_days, 365)
    # Load enough for both periods: e.g. 14 days for "this week vs last week"
    if period_a_days is not None and period_b_days is not None:
        load_days = period_a_days + period_b_days
    else:
        load_days = total_days * 2
    load_days = min(load_days, 365)
    as_of = end_date
    df = load_marketing_performance(
        client_id=client_id,
        as_of_date=as_of,
        days=load_days,
        organization_id=organization_id,
    )
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "period_label", "date", "spend", "revenue", "conversions", "roas",
            ]
        )

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    else:
        return pd.DataFrame(columns=["period_label", "date", "spend", "revenue", "conversions", "roas"])

    # Define period boundaries: period A = most recent, period B = same length immediately before
    if period_a_days is not None and period_b_days is not None:
        period_a_end = end_date
        period_a_start = end_date - timedelta(days=period_a_days - 1)
        period_b_end = period_a_start - timedelta(days=1)
        period_b_start = period_b_end - timedelta(days=period_b_days - 1)
    else:
        period_a_end = end_date
        period_a_start = end_date - timedelta(days=total_days - 1)
        period_b_end = period_a_start - timedelta(days=1)
        period_b_start = period_b_end - timedelta(days=total_days - 1)

    def in_range(d, s, e):
        return s <= d <= e

    df["period_label"] = df["date"].apply(
        lambda d: period_a_label if in_range(d, period_a_start, period_a_end) else (period_b_label if in_range(d, period_b_start, period_b_end) else None)
    )
    df = df[df["period_label"].notna()]

    # Daily-level comparison (for charts)
    daily = df.groupby(["date", "period_label"], dropna=False).agg(
        spend=("spend", "sum"),
        revenue=("revenue", "sum"),
        conversions=("conversions", "sum"),
    ).reset_index()
    daily["roas"] = daily.apply(
        lambda r: (r["revenue"] / r["spend"]) if r["spend"] and r["spend"] > 0 else 0.0,
        axis=1,
    )
    daily = daily.head(MAX_ROWS)
    return daily
