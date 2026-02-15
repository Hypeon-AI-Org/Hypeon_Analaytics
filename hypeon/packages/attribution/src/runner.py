"""Attribution runner: read raw data, run fractional (or Markov if data available), write attribution_events."""
from datetime import date
from typing import Optional

import pandas as pd
from sqlmodel import Session, select

from packages.shared.src.models import AttributionEvent, RawMetaAds, RawGoogleAds, RawShopifyOrders
from packages.attribution.src.allocator import fractional_allocate
from packages.attribution.src.markov import markov_credits


def _orders_df(session: Session, start: date, end: date) -> pd.DataFrame:
    orders = session.exec(
        select(RawShopifyOrders).where(
            RawShopifyOrders.order_date >= start,
            RawShopifyOrders.order_date <= end,
        )
    ).all()
    return pd.DataFrame(
        [
            {"order_id": o.order_id, "order_date": o.order_date, "revenue": o.revenue}
            for o in orders
        ]
    )


def _daily_spend_by_channel(session: Session, start: date, end: date) -> pd.DataFrame:
    rows = []
    for rec in session.exec(
        select(RawMetaAds).where(RawMetaAds.date >= start, RawMetaAds.date <= end)
    ).all():
        rows.append({"date": rec.date, "channel": "meta", "spend": rec.spend})
    for rec in session.exec(
        select(RawGoogleAds).where(RawGoogleAds.date >= start, RawGoogleAds.date <= end)
    ).all():
        rows.append({"date": rec.date, "channel": "google", "spend": rec.spend})
    return pd.DataFrame(rows)


def run_attribution(
    session: Session,
    run_id: str,
    start_date: date,
    end_date: date,
    channel_weights: Optional[dict] = None,
    session_sequences: Optional[list] = None,
    min_sequences_for_markov: int = 10,
) -> int:
    """
    Run attribution and write to attribution_events. Uses Markov if session_sequences
    is provided and passes min_sequences_for_markov; else fractional.
    Returns number of attribution rows written.
    """
    orders = _orders_df(session, start_date, end_date)
    if orders.empty:
        return 0
    daily_spend = _daily_spend_by_channel(session, start_date, end_date)
    channels = list(daily_spend["channel"].unique()) if not daily_spend.empty else ["meta", "google"]
    weights = channel_weights
    if session_sequences is not None:
        markov_w = markov_credits(session_sequences, channels, min_sequences_for_markov)
        if markov_w is not None:
            weights = markov_w
    allocated = fractional_allocate(orders, daily_spend, channel_weights=weights)
    for order_id, event_date, channel, weight, allocated_revenue in allocated:
        session.add(
            AttributionEvent(
                order_id=order_id,
                channel=channel,
                campaign_id=None,
                cost_center=None,
                weight=weight,
                allocated_revenue=allocated_revenue,
                event_date=event_date,
                run_id=run_id,
            )
        )
    session.commit()
    return len(allocated)
