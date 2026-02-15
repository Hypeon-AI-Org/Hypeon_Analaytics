"""Fractional attribution: configurable weights per channel; output per-order weights and allocated revenue."""
from datetime import date
from typing import Dict, List, Tuple

import pandas as pd


def fractional_allocate(
    orders: pd.DataFrame,
    daily_spend_by_channel: pd.DataFrame,
    channel_weights: Dict[str, float] | None = None,
) -> List[Tuple[str, date, str, float, float]]:
    """
    For each order, allocate revenue to channels by spend share (or custom weights).
    orders: columns order_id, order_date, revenue
    daily_spend_by_channel: columns date, channel, spend
    channel_weights: optional override; if None, use spend share for that day.
    Returns list of (order_id, event_date, channel, weight, allocated_revenue).
    """
    if channel_weights is not None:
        total_w = sum(channel_weights.values()) or 1.0
        channel_weights = {k: v / total_w for k, v in channel_weights.items()}
    out = []
    for _, row in orders.iterrows():
        order_id = str(row["order_id"])
        order_date = row["order_date"]
        if hasattr(order_date, "date"):
            order_date = order_date.date()
        revenue = float(row["revenue"])
        day_spend = daily_spend_by_channel[daily_spend_by_channel["date"] == order_date]
        if channel_weights:
            for ch, w in channel_weights.items():
                out.append((order_id, order_date, ch, w, revenue * w))
            continue
        if day_spend.empty:
            continue
        total_spend = day_spend["spend"].sum()
        if total_spend <= 0:
            continue
        for _, r in day_spend.iterrows():
            ch = r["channel"]
            spend = float(r["spend"])
            w = spend / total_spend
            out.append((order_id, order_date, ch, w, revenue * w))
    return out
