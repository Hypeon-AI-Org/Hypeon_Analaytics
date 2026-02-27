"""
FastAPI backend: enterprise multi-tenant, insights (paginated/top), review/apply, decision history, copilot.
All queries scoped by organization_id; no cross-client leakage.
Copilot uses Gemini when GEMINI_API_KEY or Vertex AI is configured.
"""
from __future__ import annotations

try:
    from pathlib import Path
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parents[2]  # repo root when main.py is backend/app/main.py
    _env_file = _root / ".env"
    loaded = load_dotenv(_env_file)
    if not loaded and Path.cwd() != _root:
        loaded = load_dotenv(Path.cwd() / ".env")
except Exception as _e:
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).warning("Could not load .env: %s", _e)

import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from .logging_config import configure_logging
configure_logging()

logger = logging.getLogger(__name__)

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import get_api_key, get_bq_project, get_analytics_dataset, get_cors_origins
from .config_loader import get
from .copilot_synthesizer import (
    set_llm_client,
    synthesize as copilot_synthesize,
    prepare_copilot_prompt,
    _parse_llm_response,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: wire Claude (if ANTHROPIC_API_KEY) or Gemini for Copilot; run refresh_analytics_cache (mandatory). Health blocks until cache ready."""
    try:
        import os
        _has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        _has_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        logger.info("Copilot env: ANTHROPIC_API_KEY=%s GEMINI/GOOGLE_API_KEY=%s", "set" if _has_anthropic else "not set", "set" if _has_gemini else "not set")
        from .llm_claude import is_claude_configured, make_claude_copilot_client
        from .llm_gemini import is_gemini_configured, make_gemini_copilot_client
        if is_claude_configured():
            set_llm_client(make_claude_copilot_client())
            logger.info("Copilot LLM: Claude (ANTHROPIC_API_KEY)%s", " | Gemini as fallback" if is_gemini_configured() else "")
        elif is_gemini_configured():
            set_llm_client(make_gemini_copilot_client())
            logger.info("Copilot LLM: Gemini")
        else:
            logger.warning("Copilot: no LLM configured. Set ANTHROPIC_API_KEY or GEMINI_API_KEY for chat.")
    except Exception as e:
        logger.warning("Copilot LLM setup failed: %s", e, exc_info=True)
    # Set default GCP project for ADC so "No project ID" warning is avoided
    import os
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        os.environ["GOOGLE_CLOUD_PROJECT"] = get_bq_project()
    # Mandatory: warm analytics cache on startup; health check blocks API until cache ready
    from .refresh_analytics_cache import do_refresh
    logger.info("Refreshing analytics cache (org=default, client_id=1)...")
    refresh_result = do_refresh(organization_id="default", client_id=1)
    if refresh_result.get("error"):
        logger.warning("Cache refresh had errors: %s", refresh_result.get("error"))
    else:
        logger.info("Cache ready. Updated: %s", refresh_result.get("updated", []))
    logger.info("Request logging active: every API request will be logged (METHOD path -> status | duration)")
    yield


app = FastAPI(title="HypeOn Analytics V1 API", version="2.0.0", lifespan=lifespan)


# ----- Global exception handlers (consistent JSON + logging) -----
@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    """Log 4xx/5xx and return consistent JSON."""
    if exc.status_code >= 500:
        logger.error(
            "HTTP %s %s -> %s | detail=%s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
            exc_info=False,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception):
    """Log full traceback and return 500 with safe message."""
    logger.exception(
        "Unhandled exception: %s %s -> %s | %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        str(exc)[:200],
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Check server logs.",
            }
        },
    )


app.add_middleware(CORSMiddleware, allow_origins=get_cors_origins(), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Cache-ready: block dashboard and /health until cache is ready (503)
from .middleware.cache_ready import CacheReadyMiddleware
app.add_middleware(CacheReadyMiddleware)

# Copilot rate limit: 20 req/min per user
from .middleware.rate_limit import CopilotRateLimitMiddleware
app.add_middleware(CopilotRateLimitMiddleware)

# Record dashboard API latency for /health/analytics
from .middleware.latency import DashboardLatencyMiddleware
app.add_middleware(DashboardLatencyMiddleware)

# Request logging: outermost so every API request is logged (method, path, status, duration)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        path = request.url.path or ""
        if request.query_params:
            path = f"{path}?{request.query_params}"
        logger.info("%s %s ...", request.method, path)
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "%s %s -> %s | %s ms",
            request.method,
            path,
            response.status_code,
            round(elapsed_ms, 1),
        )
        return response


app.add_middleware(RequestLogMiddleware)

# Dashboard API (reads from analytics cache only; <300ms target)
from .api.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/api/v1")

# Analysis API (queries raw staging tables in BigQuery for in-depth breakdowns)
from .api.analysis import router as analysis_router
app.include_router(analysis_router, prefix="/api/v1")


# ----- Auth and tenant context (must be before routes that use them) -----
def get_organization_id(request: Request) -> str:
    return request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "default"


def get_workspace_id(request: Request) -> Optional[str]:
    return request.headers.get("X-Workspace-Id") or None


def get_role_from_token(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return "analyst"
    if get_api_key() and request.headers.get("X-API-Key") == get_api_key():
        return "admin"
    return "viewer"


def require_role(*allowed: str):
    def dep(request: Request):
        role = get_role_from_token(request)
        if role not in allowed:
            raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Insufficient role"})
        return role
    return dep


@app.post("/api/v1/admin/refresh-cache")
def admin_refresh_cache(
    request: Request,
    _role: str = Depends(require_role("admin")),
):
    """Refresh analytics cache from BQ. Used by DAG or manual trigger. Requires admin."""
    org = get_organization_id(request)
    logger.info("Admin refresh-cache | org=%s", org)
    from .refresh_analytics_cache import do_refresh
    result = do_refresh(organization_id=org, client_id=1)
    return result


# ----- Structured error -----
def api_error(code: str, message: str, status: int = 400):
    raise HTTPException(status, detail={"code": code, "message": message})


# ----- Schemas -----
class InsightReviewBody(BaseModel):
    status: str = Field(..., pattern="^(reviewed|rejected)$")


class InsightApplyBody(BaseModel):
    applied_by: Optional[str] = None
    outcome_metrics_7d: Optional[str] = None
    outcome_metrics_30d: Optional[str] = None


class CopilotQueryBody(BaseModel):
    insight_id: str


class CopilotChatBody(BaseModel):
    message: str = ""
    session_id: Optional[str] = None
    client_id: Optional[int] = None


class SimulateBudgetShiftBody(BaseModel):
    client_id: int
    date: str
    from_campaign: str
    to_campaign: str
    amount: float = Field(..., gt=0)


# ----- Helpers -----
def _bq():
    from .clients.bigquery import get_client
    return get_client()


def _serialize_item(r: dict) -> dict:
    out = {}
    for k, v in r.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, (list, tuple)) and v and hasattr(v[0], "_fields"):
            out[k] = [dict(x) for x in v]
        else:
            out[k] = v
    return out


def _list_insights_scoped(
    organization_id: str,
    client_id: Optional[int],
    workspace_id: Optional[str],
    status: Optional[str],
    limit: int,
    offset: int,
) -> list[dict]:
    from .clients.bigquery import list_insights
    return list_insights(organization_id, client_id=client_id, workspace_id=workspace_id, status=status, limit=limit, offset=offset)


def _top_insights_scoped(organization_id: str, client_id: Optional[int], top_n: int) -> list[dict]:
    from .clients.bigquery import list_insights
    from .insight_ranker import top_per_client
    rows = list_insights(organization_id, client_id=client_id, status=None, limit=500, offset=0)
    ranked = top_per_client(rows, top_n=top_n)
    return ranked


def _top_decisions_scoped(organization_id: str, client_id: Optional[int], top_n: int) -> list[dict]:
    from .clients.bigquery import list_insights
    from .top_decisions import top_decisions
    rows = list_insights(organization_id, client_id=client_id, status=None, limit=200, offset=0)
    return top_decisions(rows, top_n=top_n, status_filter="new")


def _update_insight_status(insight_id: str, organization_id: str, status: str, user_id: Optional[str]) -> None:
    from .clients.bigquery import get_client, get_analytics_dataset
    client = get_client()
    project = get_bq_project()
    dataset = get_analytics_dataset()
    user = (user_id or "unknown").replace("'", "''")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    q = f"""
    UPDATE `{project}.{dataset}.analytics_insights`
    SET status = '{status}', applied_at = CURRENT_TIMESTAMP(), history = CONCAT(COALESCE(history, ''), '; applied_by={user} at {now}')
    WHERE insight_id = '{insight_id.replace("'", "''")}' AND organization_id = '{organization_id.replace("'", "''")}'
    """
    client.query(q).result()


# ----- Endpoints -----
@app.get("/insights")
def get_insights(
    request: Request,
    client_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Paginated insights scoped by organization. Returns empty list on error so UI can load."""
    org = get_organization_id(request)
    workspace = get_workspace_id(request)
    try:
        items = _list_insights_scoped(org, client_id, workspace, status, limit, offset)
    except Exception as e:
        logger.warning(
            "list_insights failed | org=%s client_id=%s error=%s",
            org, client_id, str(e)[:300],
            exc_info=True,
        )
        items = []
    return {"items": [_serialize_item(r) for r in items], "count": len(items), "organization_id": org}


@app.get("/insights/top")
def get_insights_top(
    request: Request,
    client_id: Optional[int] = Query(None),
    top_n: int = Query(None, ge=1, le=50),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Top N actionable insights per client (default from config)."""
    org = get_organization_id(request)
    n = top_n or get("top_insights_per_client", 5)
    items = _top_insights_scoped(org, client_id, n)
    return {"items": [_serialize_item(r) for r in items], "count": len(items), "organization_id": org}


@app.post("/insights/{insight_id}/review")
def insight_review(
    insight_id: str,
    body: InsightReviewBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst")),
):
    """Move insight to reviewed or rejected."""
    org = get_organization_id(request)
    _update_insight_status(insight_id, org, body.status, None)
    return {"ok": True, "insight_id": insight_id, "status": body.status}


@app.post("/insights/{insight_id}/apply")
def insight_apply(
    insight_id: str,
    body: InsightApplyBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst")),
):
    """Mark insight as applied; write to decision_history (NEW -> APPLIED)."""
    org = get_organization_id(request)
    from .clients.bigquery import get_insight_by_id, insert_decision_history
    insight = get_insight_by_id(insight_id, org)
    if not insight:
        api_error("NOT_FOUND", "Insight not found", 404)
    client_id = int(insight.get("client_id") or 0)
    insert_decision_history(
        organization_id=org,
        client_id=client_id,
        insight_id=insight_id,
        recommended_action=insight.get("recommendation") or "",
        status="applied",
        applied_by=body.applied_by,
        workspace_id=get_workspace_id(request),
    )
    _update_insight_status(insight_id, org, "applied", body.applied_by)
    from .audit_logger import log_decision_applied
    log_decision_applied(org, insight_id, body.applied_by)
    return {"ok": True, "insight_id": insight_id, "status": "applied"}


@app.get("/decisions/top")
def get_decisions_top(
    request: Request,
    client_id: Optional[int] = Query(None),
    top_n: int = Query(None, ge=1, le=20),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Top N actions today for executives (default 3). Ranked by impact × confidence × urgency × recency."""
    org = get_organization_id(request)
    n = top_n or get("top_decisions_n", 3)
    items = _top_decisions_scoped(org, client_id, n)
    return {"items": [_serialize_item(r) for r in items], "count": len(items), "organization_id": org}


@app.get("/decisions/history")
def get_decisions_history(
    request: Request,
    client_id: Optional[int] = Query(None),
    insight_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Decision lifecycle history scoped by organization."""
    org = get_organization_id(request)
    from .clients.bigquery import get_decision_history
    items = get_decision_history(org, client_id=client_id, insight_id=insight_id, status=status, limit=limit)
    return {"items": [_serialize_item(r) for r in items], "count": len(items), "organization_id": org}


def _copilot_stream_gen(insight_id: str, org: str):
    """Generator yielding SSE events: phase loading | generating | chunk | done. Any exception yields error phase (no 500)."""
    def emit(ev: dict) -> str:
        return "data: " + json.dumps(ev) + "\n\n"

    try:
        yield emit({"phase": "loading", "message": "Accessing insights & decision history…"})
        prompt, err = prepare_copilot_prompt(insight_id, organization_id=org)
        if err is not None:
            yield emit({"phase": "error", "error": err.get("error", "Unknown error")})
            return

        yield emit({"phase": "generating", "message": "Generating analysis…"})
        from .llm_claude import is_claude_configured, stream_claude
        from .llm_gemini import is_gemini_configured, stream_gemini
        if is_claude_configured():
            stream_fn = stream_claude
        elif is_gemini_configured():
            stream_fn = stream_gemini
        else:
            yield emit({"phase": "error", "error": "No LLM configured. Set ANTHROPIC_API_KEY or GEMINI_API_KEY."})
            return
        acc = []
        for chunk in stream_fn(prompt):
            acc.append(chunk)
            yield emit({"phase": "chunk", "text": chunk})
        full = "".join(acc)
        out = _parse_llm_response(full)
        out["insight_id"] = insight_id
        out["provenance"] = out.get("provenance") or "analytics_insights, decision_history, supporting_metrics_snapshot"
        yield emit({"phase": "done", "data": out})
    except Exception as e:
        logger.exception("Copilot stream failed")
        yield emit({"phase": "error", "error": str(e)[:300]})


@app.post("/copilot/query")
@app.post("/copilot_query")
def copilot_query(
    body: CopilotQueryBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Synthesized explanation from grounded sources only (insights + decision_history + snapshot)."""
    org = get_organization_id(request)
    from .audit_logger import log_copilot_query
    log_copilot_query(org, body.insight_id)
    out = copilot_synthesize(insight_id=body.insight_id, organization_id=org)
    if "error" in out:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": out["error"]})
    return out


@app.post("/copilot/stream")
def copilot_stream(
    body: CopilotQueryBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Stream Copilot response with phases: loading, generating, chunk, done. SSE."""
    org = get_organization_id(request)
    from .audit_logger import log_copilot_query
    log_copilot_query(org, body.insight_id)
    return StreamingResponse(
        _copilot_stream_gen(body.insight_id, org),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ----- V1 Copilot (chat only: LLM + run_sql) -----
@app.post("/api/v1/copilot/chat")
def copilot_chat(
    body: CopilotChatBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Chat: every query is handled by the LLM with tools. No hardcoded routing; LLM analyzes and responds dynamically."""
    org = get_organization_id(request)
    logger.info("Copilot chat | org=%s session_id=%s", org, body.session_id or "(new)")
    try:
        from .copilot.chat_handler import chat
        import uuid
        msg = (body.message or "").strip()
        sid = body.session_id or str(uuid.uuid4())
        if not msg:
            return {"text": "Please type a message to get a response.", "session_id": sid}
        out = chat(org, msg, session_id=sid, client_id=body.client_id)
        # Last-resort: never send the raw LLM error to the client
        text = (out.get("text") or "").strip()
        if text and ("couldn't complete" in text.lower() or "couldnt complete" in text.lower()):
            out = {**out, "text": "I'm having trouble right now. Please try again in a moment, or ask something like \"What should I do today?\" for a performance summary."}
        return out
    except Exception as e:
        logger.exception(
            "Copilot chat failed | org=%s session_id=%s error=%s",
            org, body.session_id or "(new)", str(e)[:200],
        )
        msg = (body.message or "").strip().lower()
        if msg in ("hi", "hello", "hey", "howdy", "hi there", "hello there", "yo"):
            return {
                "text": "Hi! How can I help with your marketing analytics today? You can ask for a performance summary, top campaigns, funnel metrics, or anything else.",
                "session_id": body.session_id or "",
            }
        return {
            "text": "I'm having trouble right now. Please try again in a moment, or ask something like \"What should I do today?\" for a performance summary. If this keeps happening, check that ANTHROPIC_API_KEY or GEMINI_API_KEY is set.",
            "session_id": body.session_id or "",
        }


@app.get("/api/v1/copilot/chat/history")
def copilot_chat_history(
    request: Request,
    session_id: str = Query(..., description="Session to load"),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Return message history for a chat session (for restoring UI after refresh)."""
    org = get_organization_id(request)
    from .copilot.session_memory import get_session_store
    store = get_session_store()
    messages = store.get_messages(org, session_id)
    return {"session_id": session_id, "messages": messages}


@app.get("/api/v1/copilot/sessions")
def copilot_sessions(
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Return list of chat sessions for the org (title, session_id, updated_at) for history UI."""
    org = get_organization_id(request)
    from .copilot.session_memory import get_session_store
    store = get_session_store()
    sessions = store.get_sessions(org)
    return {"sessions": sessions}


@app.post("/simulate_budget_shift")
def simulate_budget_shift(
    body: SimulateBudgetShiftBody,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    from .simulation import simulate_budget_shift as run_sim
    return run_sim(
        client_id=body.client_id,
        date_str=body.date,
        from_campaign=body.from_campaign,
        to_campaign=body.to_campaign,
        amount=body.amount,
    )


@app.get("/health")
def health():
    """Liveness: 503 until cache ready (middleware). Once ready, returns ok."""
    from .analytics_cache import get_cache_ready
    if not get_cache_ready():
        raise HTTPException(503, detail={"code": "CACHE_NOT_READY", "message": "Analytics cache not ready"})
    return {"status": "ok"}


@app.get("/health/analytics")
def health_analytics():
    """Observability: cache_last_refresh, cache_status, cache_age_seconds, cache_stale, latency_avg."""
    from .analytics_cache import (
        get_cache_ready,
        get_cache_last_refresh,
        get_cache_age_seconds,
        is_cache_stale,
        get_latency_avg_ms,
    )
    ready = get_cache_ready()
    last_refresh = get_cache_last_refresh()
    age_sec = get_cache_age_seconds()
    stale = is_cache_stale()
    latency_avg = get_latency_avg_ms()
    return {
        "cache_status": "ready" if ready else "empty",
        "cache_last_refresh": last_refresh,
        "cache_age_seconds": round(age_sec, 1) if age_sec is not None else None,
        "cache_stale": stale,
        "latency_avg_ms": round(latency_avg, 2) if latency_avg is not None else None,
    }


@app.get("/system/health")
def system_health(
    request: Request,
    agent_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """System health: agent_runtime, failures, insight_volume, processing_latency from system_health table."""
    org = get_organization_id(request)
    from .clients.bigquery import get_system_health_latest
    rows = get_system_health_latest(org, agent_name=agent_name, limit=limit)
    return {
        "items": [_serialize_item(r) for r in rows],
        "count": len(rows),
        "organization_id": org,
    }


# Backward-compat alias
class RecommendationApplyBody(BaseModel):
    insight_id: str
    status: str = Field("applied", pattern="^(applied|rejected)$")
    user_id: Optional[str] = None


@app.post("/recommendations/apply")
def recommendations_apply_legacy(
    body: RecommendationApplyBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst")),
):
    org = get_organization_id(request)
    _update_insight_status(body.insight_id, org, body.status, body.user_id)
    return {"ok": True, "insight_id": body.insight_id, "status": body.status}
