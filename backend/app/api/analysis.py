"""
Analysis API: in-depth Google Ads and Google Analytics breakdowns from raw staging tables.
Queries BigQuery directly (not cache) for deep analysis with date-range flexibility.
"""
from __future__ import annotations

import logging
import math
import time
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _get_organization_id(request: Request) -> str:
    return request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "default"


def _resolve_dates(
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[date, date]:
    """Resolve date range from either preset days or explicit start/end."""
    today = date.today()
    if start_date and end_date:
        return date.fromisoformat(start_date), date.fromisoformat(end_date)
    d = days or 30
    return today - timedelta(days=d), today


def _safe_div(a: float, b: float) -> float:
    if not b:
        return 0.0
    result = a / b
    if math.isnan(result) or math.isinf(result):
        return 0.0
    return result


def _safe_float(v) -> float:
    if v is None:
        return 0.0
    try:
        f = float(v)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return 0.0


def _serialize_value(v) -> float | str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    except (TypeError, ValueError):
        return str(v)


# ---------------------------------------------------------------------------
# Google Ads Analysis
# ---------------------------------------------------------------------------
@router.get("/google-ads")
def google_ads_analysis(
    request: Request,
    client_id: Optional[int] = Query(1),
    days: Optional[int] = Query(None, ge=1, le=365),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """In-depth Google Ads analysis: overview KPIs, daily timeseries, campaign/device/ad-group breakdowns."""
    org = _get_organization_id(request)
    logger.info("Analysis: google-ads | org=%s client_id=%s days=%s", org, client_id, days)
    t0 = time.perf_counter()
    sd, ed = _resolve_dates(days, start_date, end_date)
    cid = client_id or 1

    from ..clients.bigquery import load_ads_staging
    df = load_ads_staging(client_id=cid, start_date=sd, end_date=ed)

    if df is None or df.empty:
        return {
            "overview": {},
            "daily_timeseries": [],
            "by_campaign": [],
            "by_device": [],
            "by_ad_group": [],
            "date_range": {"start": sd.isoformat(), "end": ed.isoformat()},
        }

    # --- Overview KPIs ---
    total_spend = _safe_float(df["spend"].sum())
    total_clicks = _safe_float(df["clicks"].sum())
    total_impressions = _safe_float(df["impressions"].sum())
    total_conversions = _safe_float(df["conversions"].sum())
    total_revenue = _safe_float(df["revenue"].sum())

    overview = {
        "spend": round(total_spend, 2),
        "clicks": int(total_clicks),
        "impressions": int(total_impressions),
        "conversions": round(total_conversions, 2),
        "revenue": round(total_revenue, 2),
        "roas": round(_safe_div(total_revenue, total_spend), 2),
        "avg_cpc": round(_safe_div(total_spend, total_clicks), 2),
        "ctr": round(_safe_div(total_clicks, total_impressions) * 100, 2),
        "cpa": round(_safe_div(total_spend, total_conversions), 2),
    }

    # --- Daily timeseries ---
    import pandas as pd
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby("date").agg(
        spend=("spend", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index().sort_values("date")
    daily_ts = []
    for _, row in daily.iterrows():
        daily_ts.append({
            "date": row["date"].strftime("%Y-%m-%d"),
            "spend": round(_safe_float(row["spend"]), 2),
            "clicks": int(_safe_float(row["clicks"])),
            "impressions": int(_safe_float(row["impressions"])),
            "conversions": round(_safe_float(row["conversions"]), 2),
            "revenue": round(_safe_float(row["revenue"]), 2),
        })

    # --- By campaign ---
    camp = df.groupby("campaign_id", dropna=False).agg(
        spend=("spend", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    by_campaign = []
    for _, row in camp.iterrows():
        sp = _safe_float(row["spend"])
        cl = _safe_float(row["clicks"])
        imp = _safe_float(row["impressions"])
        conv = _safe_float(row["conversions"])
        rev = _safe_float(row["revenue"])
        by_campaign.append({
            "campaign_id": str(row.get("campaign_id") or ""),
            "spend": round(sp, 2),
            "clicks": int(cl),
            "impressions": int(imp),
            "conversions": round(conv, 2),
            "revenue": round(rev, 2),
            "roas": round(_safe_div(rev, sp), 2),
            "cpa": round(_safe_div(sp, conv), 2),
            "ctr": round(_safe_div(cl, imp) * 100, 2),
        })
    by_campaign.sort(key=lambda x: x["spend"], reverse=True)

    # --- By device ---
    dev = df.groupby("device", dropna=False).agg(
        spend=("spend", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    by_device = []
    for _, row in dev.iterrows():
        sp = _safe_float(row["spend"])
        cl = _safe_float(row["clicks"])
        imp = _safe_float(row["impressions"])
        conv = _safe_float(row["conversions"])
        rev = _safe_float(row["revenue"])
        by_device.append({
            "device": str(row.get("device") or "unknown"),
            "spend": round(sp, 2),
            "clicks": int(cl),
            "impressions": int(imp),
            "conversions": round(conv, 2),
            "revenue": round(rev, 2),
        })

    # --- By ad group ---
    ag = df.groupby(["campaign_id", "ad_group_id"], dropna=False).agg(
        spend=("spend", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    by_ad_group = []
    for _, row in ag.iterrows():
        sp = _safe_float(row["spend"])
        cl = _safe_float(row["clicks"])
        imp = _safe_float(row["impressions"])
        conv = _safe_float(row["conversions"])
        rev = _safe_float(row["revenue"])
        by_ad_group.append({
            "campaign_id": str(row.get("campaign_id") or ""),
            "ad_group_id": str(row.get("ad_group_id") or ""),
            "spend": round(sp, 2),
            "clicks": int(cl),
            "impressions": int(imp),
            "conversions": round(conv, 2),
            "revenue": round(rev, 2),
            "roas": round(_safe_div(rev, sp), 2),
            "ctr": round(_safe_div(cl, imp) * 100, 2),
        })
    by_ad_group.sort(key=lambda x: x["spend"], reverse=True)
    by_ad_group = by_ad_group[:50]

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("google_ads_analysis latency_ms=%.0f rows=%d", elapsed_ms, len(df))

    return {
        "overview": overview,
        "daily_timeseries": daily_ts,
        "by_campaign": by_campaign,
        "by_device": by_device,
        "by_ad_group": by_ad_group,
        "date_range": {"start": sd.isoformat(), "end": ed.isoformat()},
    }


# ---------------------------------------------------------------------------
# Google Analytics Analysis
# ---------------------------------------------------------------------------
@router.get("/google-analytics")
def google_analytics_analysis(
    request: Request,
    client_id: Optional[int] = Query(1),
    days: Optional[int] = Query(None, ge=1, le=365),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """In-depth Google Analytics analysis: overview KPIs, daily timeseries, device breakdown, conversion funnel."""
    org = _get_organization_id(request)
    logger.info("Analysis: google-analytics | org=%s client_id=%s days=%s", org, client_id, days)
    t0 = time.perf_counter()
    sd, ed = _resolve_dates(days, start_date, end_date)
    cid = client_id or 1

    from ..clients.bigquery import load_ga4_staging
    df = load_ga4_staging(client_id=cid, start_date=sd, end_date=ed)

    if df is None or df.empty:
        return {
            "overview": {},
            "daily_timeseries": [],
            "by_device": [],
            "conversion_funnel": [],
            "date_range": {"start": sd.isoformat(), "end": ed.isoformat()},
        }

    # --- Overview KPIs ---
    total_sessions = _safe_float(df["sessions"].sum())
    total_conversions = _safe_float(df["conversions"].sum())
    total_revenue = _safe_float(df["revenue"].sum())

    overview = {
        "sessions": int(total_sessions),
        "conversions": round(total_conversions, 2),
        "revenue": round(total_revenue, 2),
        "conversion_rate": round(_safe_div(total_conversions, total_sessions) * 100, 2),
        "revenue_per_session": round(_safe_div(total_revenue, total_sessions), 2),
    }

    # --- Daily timeseries ---
    import pandas as pd
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby("date").agg(
        sessions=("sessions", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index().sort_values("date")
    daily_ts = []
    for _, row in daily.iterrows():
        daily_ts.append({
            "date": row["date"].strftime("%Y-%m-%d"),
            "sessions": int(_safe_float(row["sessions"])),
            "conversions": round(_safe_float(row["conversions"]), 2),
            "revenue": round(_safe_float(row["revenue"]), 2),
        })

    # --- By device ---
    dev = df.groupby("device", dropna=False).agg(
        sessions=("sessions", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    by_device = []
    for _, row in dev.iterrows():
        sess = _safe_float(row["sessions"])
        conv = _safe_float(row["conversions"])
        rev = _safe_float(row["revenue"])
        by_device.append({
            "device": str(row.get("device") or "unknown"),
            "sessions": int(sess),
            "conversions": round(conv, 2),
            "revenue": round(rev, 2),
            "conversion_rate": round(_safe_div(conv, sess) * 100, 2),
        })

    # --- Conversion funnel ---
    conv_rate = _safe_div(total_conversions, total_sessions)
    funnel = [
        {
            "stage": "Sessions",
            "value": int(total_sessions),
            "drop_pct": None,
        },
        {
            "stage": "Conversions",
            "value": round(total_conversions, 2),
            "drop_pct": round((1 - conv_rate) * 100, 1) if total_sessions else 0,
        },
        {
            "stage": "Revenue",
            "value": round(total_revenue, 2),
            "drop_pct": None,
        },
    ]

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("google_analytics_analysis latency_ms=%.0f rows=%d", elapsed_ms, len(df))

    return {
        "overview": overview,
        "daily_timeseries": daily_ts,
        "by_device": by_device,
        "conversion_funnel": funnel,
        "date_range": {"start": sd.isoformat(), "end": ed.isoformat()},
    }
