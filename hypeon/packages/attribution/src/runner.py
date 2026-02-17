"""Attribution runner: read raw data, run fractional (or Markov if data available), write attribution_events."""
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlmodel import Session, select

from packages.shared.src.models import AttributionEvent, RawMetaAds, RawGoogleAds, RawShopifyOrders
from packages.attribution.src.allocator import fractional_allocate
from packages.attribution.src.markov import markov_credits
from packages.attribution.src.diagnostics import run_diagnostics
from packages.governance.src.versions import MTA_VERSION


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


def _synthetic_sequences_from_allocated(
    allocated: List[Tuple[str, date, str, float, float]],
    channels: List[str],
) -> List[List[str]]:
    """Build synthetic path sequences from allocated (order_id, date, channel, weight, revenue). One path per order = [channels ordered by weight desc]."""
    from collections import defaultdict
    by_order: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for order_id, _date, channel, weight, _rev in allocated:
        by_order[order_id].append((channel, weight))
    sequences = []
    for order_id, pairs in by_order.items():
        pairs.sort(key=lambda x: -x[1])
        sequences.append([p[0] for p in pairs])
    return sequences


def _core_attribution_logic(
    session: Session,
    run_id: str,
    start_date: date,
    end_date: date,
    channel_weights: Optional[Dict[str, float]] = None,
    session_sequences: Optional[List[List[str]]] = None,
    min_sequences_for_markov: int = 10,
) -> Tuple[int, Dict[str, float], List[Tuple[str, date, str, float, float]]]:
    """
    Shared attribution logic: load orders and spend, compute weights (Markov or fractional),
    write attribution_events, return (number_written, allocations_dict, allocated).
    allocations_dict: channel -> share of total attributed (0..1).
    allocated: list of (order_id, event_date, channel, weight, allocated_revenue) for diagnostics.
    """
    orders = _orders_df(session, start_date, end_date)
    if orders.empty:
        return 0, {}, []
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
                weight=float(weight),
                allocated_revenue=float(allocated_revenue),
                event_date=event_date,
                run_id=run_id,
            )
        )
    session.commit()
    n_written = len(allocated)
    total_by_ch: Dict[str, float] = {}
    for _oid, _date, ch, _w, rev in allocated:
        total_by_ch[ch] = total_by_ch.get(ch, 0.0) + rev
    total_rev = sum(total_by_ch.values()) or 1.0
    allocations_dict = {ch: total_by_ch.get(ch, 0.0) / total_rev for ch in channels}
    return n_written, allocations_dict, allocated


def run_attribution(
    session: Session,
    run_id: str,
    start_date: date,
    end_date: date,
    channel_weights: Optional[Dict[str, float]] = None,
    session_sequences: Optional[List[List[str]]] = None,
    min_sequences_for_markov: int = 10,
) -> int:
    """
    Run attribution and write to attribution_events. Uses Markov if session_sequences
    is provided and passes min_sequences_for_markov; else fractional.
    Returns number of attribution rows written.
    """
    n_written, _, _ = _core_attribution_logic(
        session, run_id, start_date, end_date,
        channel_weights=channel_weights,
        session_sequences=session_sequences,
        min_sequences_for_markov=min_sequences_for_markov,
    )
    return n_written


def run_attribution_with_diagnostics(
    session: Session,
    run_id: str,
    start_date: date,
    end_date: date,
    channel_weights: Optional[Dict[str, float]] = None,
    session_sequences: Optional[List[List[str]]] = None,
    min_sequences_for_markov: int = 10,
    mta_version: Optional[str] = None,
) -> Tuple[int, Dict]:
    """
    Run attribution via _core_attribution_logic, then run diagnostics and return
    (n_written, {"run_id", "version", "timestamp", "allocations", "diagnostics", "confidence_score"}).
    If session_sequences is None, builds synthetic sequences from the allocated list returned by core logic.
    """
    n_written, allocations_dict, allocated = _core_attribution_logic(
        session, run_id, start_date, end_date,
        channel_weights=channel_weights,
        session_sequences=session_sequences,
        min_sequences_for_markov=min_sequences_for_markov,
    )
    channels = list(allocations_dict.keys()) if allocations_dict else ["meta", "google"]
    sequences = session_sequences
    if sequences is None and allocated:
        sequences = _synthetic_sequences_from_allocated(allocated, channels)
    if not sequences:
        sequences = []
    diagnostics = run_diagnostics(sequences, channels=channels)
    return n_written, {
        "run_id": run_id,
        "version": mta_version or MTA_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "allocations": allocations_dict,
        "diagnostics": diagnostics,
        "confidence_score": diagnostics["confidence_score"],
    }
