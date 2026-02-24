"""
Analytics Serving Layer: Redis (Option A) or in-memory fallback.
Dashboard endpoints read ONLY from this cache. Target <300ms.
Populated by refresh_analytics_cache on startup; health blocks until cache ready.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

from .cache_backend import (
    cache_get,
    cache_set,
    cache_get_all,
    cache_set_all,
    cache_has_any,
)

# Default client_id when not specified
DEFAULT_CLIENT_ID = 1

# Cache readiness: set True after first successful refresh (startup or admin)
_cache_ready = False
_cache_last_refresh: Optional[float] = None
_lock_ready = threading.Lock()

# Freshness guard: if cache older than this, API returns "Refreshing data" (503)
CACHE_STALE_SECONDS = 30 * 60  # 30 minutes

# Dashboard API latency (last N requests, ms) for /health/analytics
_latency_samples: list[float] = []
_latency_max_samples = 100
_latency_lock = threading.Lock()


def _key(organization_id: str, client_id: Optional[int]) -> tuple[str, int]:
    return (organization_id or "default", int(client_id) if client_id is not None else DEFAULT_CLIENT_ID)


def set_cache_ready(ready: bool = True) -> None:
    with _lock_ready:
        global _cache_ready
        _cache_ready = ready


def get_cache_ready() -> bool:
    with _lock_ready:
        return _cache_ready


def set_cache_last_refresh(ts: Optional[float] = None) -> None:
    global _cache_last_refresh
    _cache_last_refresh = ts or time.time()


def get_cache_last_refresh() -> Optional[float]:
    return _cache_last_refresh


def get_cache_age_seconds() -> Optional[float]:
    """Seconds since last refresh, or None if never refreshed."""
    if _cache_last_refresh is None:
        return None
    return time.time() - _cache_last_refresh


def is_cache_stale() -> bool:
    """True if cache is older than CACHE_STALE_SECONDS (e.g. DAG failed)."""
    age = get_cache_age_seconds()
    return age is not None and age > CACHE_STALE_SECONDS


def record_dashboard_latency_ms(ms: float) -> None:
    with _latency_lock:
        _latency_samples.append(ms)
        if len(_latency_samples) > _latency_max_samples:
            _latency_samples.pop(0)


def get_latency_avg_ms() -> Optional[float]:
    with _latency_lock:
        if not _latency_samples:
            return None
        return sum(_latency_samples) / len(_latency_samples)


def get_cached_business_overview(
    organization_id: str,
    client_id: Optional[int] = None,
) -> Optional[dict]:
    org, cid = _key(organization_id, client_id)
    data = cache_get(org, cid, "business_overview")
    return data if isinstance(data, dict) else None


def get_cached_campaign_performance(
    organization_id: str,
    client_id: Optional[int] = None,
) -> list[dict]:
    org, cid = _key(organization_id, client_id)
    data = cache_get(org, cid, "campaign_performance")
    return data if isinstance(data, list) else []


def get_cached_funnel(
    organization_id: str,
    client_id: Optional[int] = None,
) -> Optional[dict]:
    org, cid = _key(organization_id, client_id)
    data = cache_get(org, cid, "funnel")
    return data if isinstance(data, dict) else None


def get_cached_actions(
    organization_id: str,
    client_id: Optional[int] = None,
) -> list[dict]:
    org, cid = _key(organization_id, client_id)
    data = cache_get(org, cid, "actions")
    return data if isinstance(data, list) else []


def refresh_cache_for_org_client(
    organization_id: str,
    client_id: int,
    *,
    business_overview: Optional[dict] = None,
    campaign_performance: Optional[list[dict]] = None,
    funnel: Optional[dict] = None,
    actions: Optional[list[dict]] = None,
) -> None:
    org, cid = _key(organization_id, client_id)
    data = {}
    if business_overview is not None:
        data["business_overview"] = business_overview
    if campaign_performance is not None:
        data["campaign_performance"] = campaign_performance
    if funnel is not None:
        data["funnel"] = funnel
    if actions is not None:
        data["actions"] = actions
    if data:
        cache_set_all(org, cid, data)
