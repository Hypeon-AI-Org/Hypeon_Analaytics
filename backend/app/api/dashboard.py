"""
Dashboard API: read-only from Analytics Serving Layer (cache). Target <300ms.
All endpoints read from analytics_cache; no BigQuery in request path.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request

from ..analytics_cache import (
    get_cached_actions,
    get_cached_business_overview,
    get_cached_campaign_performance,
    get_cached_funnel,
)


def get_organization_id(request: Request) -> str:
    return request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "default"


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)


@router.get("/business-overview")
def business_overview(
    request: Request,
    client_id: Optional[int] = None,
):
    """Return total_revenue, total_spend, blended_roas, conversion_rate, revenue_trend_7d, spend_trend_7d from cache."""
    org = get_organization_id(request)
    logger.info("Dashboard: business-overview | org=%s client_id=%s", org, client_id)
    data = get_cached_business_overview(org, client_id)
    if data is None:
        return {
            "total_revenue": 0,
            "total_spend": 0,
            "blended_roas": 0,
            "conversion_rate": 0,
            "revenue_trend_7d": 0,
            "spend_trend_7d": 0,
        }
    return data


@router.get("/campaign-performance")
def campaign_performance(
    request: Request,
    client_id: Optional[int] = None,
):
    """Return list of { campaign, spend, revenue, roas, status } from cache."""
    org = get_organization_id(request)
    logger.info("Dashboard: campaign-performance | org=%s client_id=%s", org, client_id)
    items = get_cached_campaign_performance(org, client_id)
    return {"items": items, "count": len(items)}


@router.get("/funnel")
def funnel(
    request: Request,
    client_id: Optional[int] = None,
):
    """Return clicks, sessions, purchases, drop_percentages from cache."""
    org = get_organization_id(request)
    logger.info("Dashboard: funnel | org=%s client_id=%s", org, client_id)
    data = get_cached_funnel(org, client_id)
    if data is None:
        return {"clicks": 0, "sessions": 0, "purchases": 0, "drop_percentages": []}
    return data


@router.get("/actions")
def actions(
    request: Request,
    client_id: Optional[int] = None,
):
    """Return top actions (increase_budget, reduce_budget, investigate) from cache."""
    org = get_organization_id(request)
    logger.info("Dashboard: actions | org=%s client_id=%s", org, client_id)
    items = get_cached_actions(org, client_id)
    return {"items": items, "count": len(items)}
