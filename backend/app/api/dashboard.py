"""
Dashboard API: read-only from Analytics Serving Layer (cache). Target <300ms.
All endpoints read from analytics_cache; no BigQuery in request path.
Always return 200 with JSON-serializable body (never 500).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..analytics_cache import (
    get_cached_business_overview,
    get_cached_campaign_performance,
    get_cached_funnel,
)


def _org_id(request: Request) -> str:
    try:
        return request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "default"
    except Exception:
        return "default"


def _safe_client_id(client_id: Any) -> Optional[int]:
    """Coerce client_id to int or None; never raise."""
    if client_id is None:
        return None
    try:
        return int(client_id)
    except (TypeError, ValueError):
        return None


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)


@router.get("/ping")
def dashboard_ping():
    """Always 200. Use to verify backend connectivity from the frontend."""
    return JSONResponse(status_code=200, content={"ok": True, "service": "dashboard"})


def _safe_overview() -> dict:
    """Default overview when cache fails or errors."""
    return {
        "total_revenue": 0,
        "total_spend": 0,
        "blended_roas": 0,
        "conversion_rate": 0,
        "revenue_trend_7d": 0,
        "spend_trend_7d": 0,
    }


def _json_serializable(obj: Any) -> Any:
    """Return a JSON-serializable copy (dates -> str, etc.)."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_serializable(v) for v in obj]
    return obj


@router.get("/business-overview")
def business_overview(
    request: Request,
    client_id: Optional[int] = None,
):
    """Return total_revenue, total_spend, etc. from cache. Never 500."""
    try:
        org = _org_id(request)
        cid = _safe_client_id(client_id)
        logger.info("Dashboard: business-overview | org=%s client_id=%s", org, cid)
        data = get_cached_business_overview(org, cid)
        if data is None:
            body = _safe_overview()
        else:
            body = _json_serializable(data)
        return JSONResponse(status_code=200, content=body)
    except Exception as e:
        logger.exception("Dashboard business-overview failed: %s", e)
        return JSONResponse(status_code=200, content=_safe_overview())


@router.get("/campaign-performance")
def campaign_performance(
    request: Request,
    client_id: Optional[int] = None,
):
    """Return list of { campaign, spend, revenue, roas, status } from cache. Never 500."""
    try:
        org = _org_id(request)
        cid = _safe_client_id(client_id)
        logger.info("Dashboard: campaign-performance | org=%s client_id=%s", org, cid)
        items = get_cached_campaign_performance(org, cid)
        body = {"items": _json_serializable(items or []), "count": len(items or [])}
        return JSONResponse(status_code=200, content=body)
    except Exception as e:
        logger.exception("Dashboard campaign-performance failed: %s", e)
        return JSONResponse(status_code=200, content={"items": [], "count": 0})


@router.get("/funnel")
def funnel(
    request: Request,
    client_id: Optional[int] = None,
):
    """Return clicks, sessions, purchases, drop_percentages from cache. Never 500."""
    try:
        org = _org_id(request)
        cid = _safe_client_id(client_id)
        logger.info("Dashboard: funnel | org=%s client_id=%s", org, cid)
        data = get_cached_funnel(org, cid)
        if data is None:
            body = {"clicks": 0, "sessions": 0, "purchases": 0, "drop_percentages": []}
        else:
            body = _json_serializable(data)
        return JSONResponse(status_code=200, content=body)
    except Exception as e:
        logger.exception("Dashboard funnel failed: %s", e)
        return JSONResponse(status_code=200, content={"clicks": 0, "sessions": 0, "purchases": 0, "drop_percentages": []})


