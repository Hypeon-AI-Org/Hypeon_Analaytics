"""
Cache-ready middleware: block dashboard (and optionally health) until cache is ready.
Returns 503 Service Unavailable so load balancer/health check blocks API until cache ready.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def _cache_ready() -> bool:
    from ..analytics_cache import get_cache_ready
    return get_cache_ready()


def _cache_stale() -> bool:
    from ..analytics_cache import is_cache_stale
    return is_cache_stale()


class CacheReadyMiddleware(BaseHTTPMiddleware):
    """Return 503 for dashboard and /health until cache is ready; 503 'Refreshing data' when cache stale (>30min)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope.get("path") or ""
        ready = _cache_ready()
        if not ready:
            if (path.startswith("/api/v1/dashboard") or path == "/health") and path != "/health/analytics":
                return JSONResponse(
                    status_code=503,
                    content={
                        "code": "CACHE_NOT_READY",
                        "message": "Analytics cache is not ready. Try again shortly.",
                    },
                )
            return await call_next(request)
        # Cache ready but may be stale: block dashboard from serving old data
        if path.startswith("/api/v1/dashboard") and _cache_stale():
            return JSONResponse(
                status_code=503,
                content={
                    "code": "CACHE_STALE",
                    "message": "Refreshing data. Please try again in a moment.",
                },
            )
        return await call_next(request)
