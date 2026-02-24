"""
Rate limit middleware: 15 req/min per user for Copilot endpoints.
Key: X-Organization-Id + client IP. Returns 429 Too Many Requests when exceeded.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# 20 requests per 60 seconds per key (per user)
RATE_LIMIT_N = 20
RATE_LIMIT_WINDOW_SEC = 60

# key -> deque of timestamps
_store: dict[str, deque] = {}
_store_lock = __import__("threading").Lock()


def _key(request: Request) -> str:
    org = request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "default"
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{org}:{ip}"


def _is_over_limit(key: str) -> bool:
    now = time.monotonic()
    with _store_lock:
        if key not in _store:
            _store[key] = deque(maxlen=RATE_LIMIT_N * 2)
        q = _store[key]
        while q and q[0] < now - RATE_LIMIT_WINDOW_SEC:
            q.popleft()
        if len(q) >= RATE_LIMIT_N:
            return True
        q.append(now)
    return False


class CopilotRateLimitMiddleware(BaseHTTPMiddleware):
    """Limit POST /api/v1/copilot/query and /api/v1/copilot/stream to 20 req/min per user."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.scope.get("path") or ""
        if request.method != "POST" or "/api/v1/copilot/" not in path:
            return await call_next(request)
        key = _key(request)
        if _is_over_limit(key):
            return JSONResponse(
                status_code=429,
                content={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many Copilot requests. Limit 20 per minute."},
            )
        return await call_next(request)
