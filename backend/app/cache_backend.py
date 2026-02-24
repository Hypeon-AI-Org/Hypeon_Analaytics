"""
Cache backend: Redis (Option A) with in-memory fallback.
If REDIS_URL is set, use Redis; otherwise in-memory dict. Same interface for analytics_cache.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Optional

_redis_client: Any = None
_redis_available: Optional[bool] = None
_lock = threading.Lock()

# In-memory fallback store (key -> JSON-serializable value)
_memory: dict[str, Any] = {}
# Prefix for Redis keys
PREFIX = "hypeon:cache:"


def _get_redis():
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client
    with _lock:
        url = os.environ.get("REDIS_URL")
        if not url:
            _redis_available = False
            return None
        try:
            import redis
            _redis_client = redis.from_url(url, decode_responses=True)
            _redis_client.ping()
            _redis_available = True
            return _redis_client
        except Exception:
            _redis_available = False
            return None


def _cache_key(organization_id: str, client_id: int, slot: str) -> str:
    return f"{PREFIX}{organization_id}:{client_id}:{slot}"


def cache_get(organization_id: str, client_id: int, slot: str) -> Any:
    """Get one cache slot (business_overview, campaign_performance, funnel, actions)."""
    key = _cache_key(organization_id, client_id, slot)
    r = _get_redis()
    if r:
        try:
            raw = r.get(key)
            if raw is not None:
                return json.loads(raw)
        except Exception:
            pass
        return None
    with _lock:
        return _memory.get(key)


def cache_set(organization_id: str, client_id: int, slot: str, value: Any) -> None:
    """Set one cache slot."""
    key = _cache_key(organization_id, client_id, slot)
    r = _get_redis()
    if r:
        try:
            r.set(key, json.dumps(value, default=str), ex=86400 * 2)
        except Exception:
            with _lock:
                _memory[key] = value
        return
    with _lock:
        _memory[key] = value


def cache_get_all(organization_id: str, client_id: int) -> dict[str, Any]:
    """Get all slots for (org, client) as dict."""
    out = {}
    for slot in ("business_overview", "campaign_performance", "funnel", "actions"):
        val = cache_get(organization_id, client_id, slot)
        if val is not None:
            out[slot] = val
    return out


def cache_set_all(organization_id: str, client_id: int, data: dict[str, Any]) -> None:
    """Set multiple slots."""
    for slot, value in data.items():
        if slot in ("business_overview", "campaign_performance", "funnel", "actions") and value is not None:
            cache_set(organization_id, client_id, slot, value)


def cache_has_any(organization_id: str, client_id: int) -> bool:
    """True if at least one slot is populated."""
    all_ = cache_get_all(organization_id, client_id)
    return len(all_) > 0
