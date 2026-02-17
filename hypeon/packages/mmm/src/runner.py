"""MMM runner: build features (adstock + saturation), fit pipeline, persist mmm_results."""
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from packages.shared.src.models import MMMResults, RawMetaAds, RawGoogleAds, RawShopifyOrders
from packages.mmm.src.transforms import adstock_transform, saturation_log
from packages.mmm.src.model import fit_pipeline
from packages.governance.src.versions import MMM_VERSION


def _daily_spend_matrix(
    session: Session,
    start: date,
    end: date,
    channels: List[str],
) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
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
    n_boot: int = 500,
    mmm_version: Optional[str] = None,
) -> Dict:
    """
    Build daily spend matrix and revenue, apply adstock + log saturation, fit via model.fit_pipeline,
    write mmm_results. Returns dict with run_id, r2, coefficients, and full diagnostics (vif,
    elasticities, bootstrap_ci, stability_index, confidence_score) for API use.
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
                    model_version=mmm_version or MMM_VERSION,
                )
            )
        session.commit()
        return {
            "run_id": run_id,
            "r2": None,
            "coefficients": {ch: 0.0 for ch in channels},
            "vif": {},
            "elasticities": {},
            "bootstrap_ci": {},
            "stability_index": 0.0,
            "confidence_score": 0.0,
        }
    pipeline_out = fit_pipeline(
        X, rev,
        channel_names=channels,
        n_boot=n_boot,
        estimator="ridge",
        model_version=mmm_version or MMM_VERSION,
    )
    coefs = pipeline_out["coefficients"]
    r2 = pipeline_out["r2"]
    for ch in channels:
        c = coefs.get(ch, 0.0)
        session.add(
            MMMResults(
                run_id=run_id,
                channel=ch,
                coefficient=c,
                goodness_of_fit_r2=r2,
                model_version=pipeline_out["model_version"],
            )
        )
    session.commit()
    return {
        "run_id": run_id,
        "r2": r2,
        "coefficients": coefs,
        "model_version": pipeline_out["model_version"],
        "adj_r2": pipeline_out["adj_r2"],
        "mape": pipeline_out["mape"],
        "vif": pipeline_out["vif"],
        "elasticities": pipeline_out["elasticities"],
        "bootstrap_ci": pipeline_out["bootstrap_ci"],
        "stability_index": pipeline_out["stability_index"],
        "confidence_score": pipeline_out["confidence_score"],
    }
