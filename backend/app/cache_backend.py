"""
Cache backend: Redis with in-memory fallback.
Uses REDIS_URL when set (works with Google Cloud Memorystore for Redis or any Redis server).
Otherwise in-memory dict; cache is lost on restart. Same interface for analytics_cache.
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
# In-memory rate limit fallback when Redis unavailable (key -> list of timestamps)
_ratelimit_memory: dict[str, list] = {}
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


# Rate limit: prefix and window (shared with middleware)
RATELIMIT_PREFIX = "hypeon:ratelimit:"
RATELIMIT_WINDOW_SEC = 60


def rate_limit_is_over_limit(key: str, limit: int = 20) -> bool:
    """
    Check and increment rate limit for key. Returns True if over limit (caller should return 429).
    Uses Redis when available so limit is shared across pods; falls back to in-memory per process.
    """
    r = _get_redis()
    if r:
        try:
            full_key = f"{RATELIMIT_PREFIX}{key}"
            count_raw = r.get(full_key)
            count = int(count_raw) if count_raw else 0
            if count >= limit:
                return True
            r.incr(full_key)
            if count == 0:
                r.expire(full_key, RATELIMIT_WINDOW_SEC)
            return False
        except Exception:
            pass
    # In-memory fallback (per-process when Redis unavailable)
    import time
    with _lock:
        if key not in _ratelimit_memory:
            _ratelimit_memory[key] = []
        ts_list = _ratelimit_memory[key]
        now = time.monotonic()
        while ts_list and ts_list[0] < now - RATELIMIT_WINDOW_SEC:
            ts_list.pop(0)
        if len(ts_list) >= limit:
            return True
        ts_list.append(now)
    return False
