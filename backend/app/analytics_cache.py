"""
Analytics Serving Layer: in-memory cache for dashboard API.
Dashboard endpoints read ONLY from this cache (no BigQuery at request time). Target <300ms.
Populated by refresh_analytics_cache script; optionally warmed on backend startup.
"""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from typing import Any, Optional

# Key: (organization_id, client_id). client_id 0 = default/aggregate.
_cache: dict[tuple[str, int], dict[str, Any]] = {}
_lock = threading.Lock()

# Default client_id when not specified
DEFAULT_CLIENT_ID = 1


def _key(organization_id: str, client_id: Optional[int]) -> tuple[str, int]:
    return (organization_id or "default", int(client_id) if client_id is not None else DEFAULT_CLIENT_ID)


def get_cached_business_overview(
    organization_id: str,
    client_id: Optional[int] = None,
) -> Optional[dict]:
    """Return cached business overview or None if not populated."""
    with _lock:
        data = _cache.get(_key(organization_id, client_id), {}).get("business_overview")
    return data


def get_cached_campaign_performance(
    organization_id: str,
    client_id: Optional[int] = None,
) -> list[dict]:
    """Return cached campaign performance list (empty if not populated)."""
    with _lock:
        data = _cache.get(_key(organization_id, client_id), {}).get("campaign_performance")
    return data if isinstance(data, list) else []


def get_cached_funnel(
    organization_id: str,
    client_id: Optional[int] = None,
) -> Optional[dict]:
    """Return cached funnel metrics or None."""
    with _lock:
        data = _cache.get(_key(organization_id, client_id), {}).get("funnel")
    return data


def get_cached_actions(
    organization_id: str,
    client_id: Optional[int] = None,
) -> list[dict]:
    """Return cached actions list (empty if not populated)."""
    with _lock:
        data = _cache.get(_key(organization_id, client_id), {}).get("actions")
    return data if isinstance(data, list) else []


def set_cached_business_overview(
    organization_id: str,
    client_id: int,
    payload: dict,
) -> None:
    with _lock:
        key = _key(organization_id, client_id)
        if key not in _cache:
            _cache[key] = {}
        _cache[key]["business_overview"] = payload


def set_cached_campaign_performance(
    organization_id: str,
    client_id: int,
    payload: list[dict],
) -> None:
    with _lock:
        key = _key(organization_id, client_id)
        if key not in _cache:
            _cache[key] = {}
        _cache[key]["campaign_performance"] = payload


def set_cached_funnel(
    organization_id: str,
    client_id: int,
    payload: dict,
) -> None:
    with _lock:
        key = _key(organization_id, client_id)
        if key not in _cache:
            _cache[key] = {}
        _cache[key]["funnel"] = payload


def set_cached_actions(
    organization_id: str,
    client_id: int,
    payload: list[dict],
) -> None:
    with _lock:
        key = _key(organization_id, client_id)
        if key not in _cache:
            _cache[key] = {}
        _cache[key]["actions"] = payload


def refresh_cache_for_org_client(
    organization_id: str,
    client_id: int,
    *,
    business_overview: Optional[dict] = None,
    campaign_performance: Optional[list[dict]] = None,
    funnel: Optional[dict] = None,
    actions: Optional[list[dict]] = None,
) -> None:
    """Set all cache entries for one (org, client). Used by refresh script."""
    with _lock:
        key = _key(organization_id, client_id)
        if key not in _cache:
            _cache[key] = {}
        if business_overview is not None:
            _cache[key]["business_overview"] = business_overview
        if campaign_performance is not None:
            _cache[key]["campaign_performance"] = campaign_performance
        if funnel is not None:
            _cache[key]["funnel"] = funnel
        if actions is not None:
            _cache[key]["actions"] = actions
