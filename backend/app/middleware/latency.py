"""Record dashboard API latency for /health/analytics."""
from __future__ import annotations

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class DashboardLatencyMiddleware(BaseHTTPMiddleware):
    """Record request duration for /api/v1/dashboard/* and feed analytics_cache."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope.get("path") or ""
        if not path.startswith("/api/v1/dashboard"):
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        try:
            from ..analytics_cache import record_dashboard_latency_ms
            record_dashboard_latency_ms(ms)
        except Exception:
            pass
        return response
