"""MMM runner: build features (adstock + saturation), fit regression, persist mmm_results."""
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from packages.shared.src.models import MMMResults, RawMetaAds, RawGoogleAds, RawShopifyOrders
from packages.mmm.src.transforms import adstock_transform, saturation_log
from packages.mmm.src.regression import fit_mmm


def _daily_spend_matrix(
    session: Session,
    start: date,
    end: date,
    channels: List[str],
) -> Tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """Return (dates, spend_matrix, revenue vector)."""
    dates = pd.date_range(start=start, end=end, freq="D")
    date_to_idx = {d.date(): i for i, d in enumerate(dates)}
    rev_by_date = {}
    for o in session.exec(
        select(RawShopifyOrders).where(
            RawShopifyOrders.order_date >= start,
            RawShopifyOrders.order_date <= end,
        )
    ).all():
        od = o.order_date
        rev_by_date[od] = rev_by_date.get(od, 0) + o.revenue
    rev = np.array([rev_by_date.get(d.date(), 0.0) for d in dates], dtype=float)
    spend_matrix = np.zeros((len(dates), len(channels)))
    for j, ch in enumerate(channels):
        if ch == "meta":
            recs = session.exec(
                select(RawMetaAds).where(RawMetaAds.date >= start, RawMetaAds.date <= end)
            ).all()
            for r in recs:
                i = date_to_idx.get(r.date)
                if i is not None:
                    spend_matrix[i, j] += r.spend
        elif ch == "google":
            recs = session.exec(
                select(RawGoogleAds).where(RawGoogleAds.date >= start, RawGoogleAds.date <= end)
            ).all()
            for r in recs:
                i = date_to_idx.get(r.date)
                if i is not None:
                    spend_matrix[i, j] += r.spend
    return dates, spend_matrix, rev


def run_mmm(
    session: Session,
    run_id: str,
    start_date: date,
    end_date: date,
    channels: Optional[List[str]] = None,
    adstock_half_life: float = 7.0,
    ridge_alpha: float = 0.0,
) -> Dict:
    """
    Build daily spend matrix and revenue, apply adstock + log saturation, fit regression, write mmm_results.
    Returns dict with run_id, r2, coefficients per channel.
    """
    if channels is None:
        channels = ["meta", "google"]
    dates, spend_matrix, rev = _daily_spend_matrix(session, start_date, end_date, channels)
    X_list = []
    for j in range(spend_matrix.shape[1]):
        adstocked = adstock_transform(spend_matrix[:, j], adstock_half_life)
        saturated = saturation_log(adstocked)
        X_list.append(saturated.reshape(-1, 1))
    X = np.hstack(X_list)
    if X.size == 0 or rev.size == 0:
        for ch in channels:
            session.add(
                MMMResults(
                    run_id=run_id,
                    channel=ch,
                    coefficient=0.0,
                    goodness_of_fit_r2=None,
                    model_version="v1",
                )
            )
        session.commit()
        return {"run_id": run_id, "r2": None, "coefficients": {ch: 0.0 for ch in channels}}
    coef, r2, _ = fit_mmm(X, rev, ridge_alpha=ridge_alpha)
    for j, ch in enumerate(channels):
        c = float(coef[j]) if j < len(coef) else 0.0
        session.add(
            MMMResults(
                run_id=run_id,
                channel=ch,
                coefficient=c,
                goodness_of_fit_r2=r2,
                model_version="v1",
            )
        )
    session.commit()
    return {"run_id": run_id, "r2": r2, "coefficients": {ch: float(coef[j]) for j, ch in enumerate(channels)}}
