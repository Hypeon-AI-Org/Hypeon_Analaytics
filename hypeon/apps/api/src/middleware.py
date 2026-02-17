"""Correlation ID and logging middleware. Do NOT wrap streaming or non-JSON responses."""
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def get_correlation_id(request: Request) -> str:
    """Read or generate correlation ID. Set on request.state in middleware."""
    return getattr(request.state, "correlation_id", "") or str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Set request.state.correlation_id from X-Correlation-ID header or generate new."""
    async def dispatch(self, request: Request, call_next):
        request.state.correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, correlation_id, status, duration."""
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        correlation_id = getattr(request.state, "correlation_id", "")
        # Structured log (no PII)
        print(f"[api] {request.method} {request.url.path} {response.status_code} correlation_id={correlation_id[:8] if correlation_id else '-'} duration_s={duration:.3f}")
        return response
