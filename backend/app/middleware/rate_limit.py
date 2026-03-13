"""
Rate limit middleware: 20 req/min per user for Copilot endpoints.
Key: X-Organization-Id + client IP. Uses Redis when REDIS_URL is set (shared across pods).
Falls back to in-memory per process when Redis is unavailable.
"""
from __future__ import annotations

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

RATE_LIMIT_N = 20


def _key(request: Request) -> str:
    org = (request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "").strip()
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{org}:{ip}"


class CopilotRateLimitMiddleware(BaseHTTPMiddleware):
    """Limit POST /api/v1/copilot/chat to 20 req/min per user. Uses Redis when available."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.scope.get("path") or ""
        if request.method != "POST" or "/api/v1/copilot/" not in path:
            return await call_next(request)
        from ..cache_backend import rate_limit_is_over_limit
        key = _key(request)
        if rate_limit_is_over_limit(key, limit=RATE_LIMIT_N):
            return JSONResponse(
                status_code=429,
                content={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many Copilot requests. Limit 20 per minute."},
            )
        return await call_next(request)
