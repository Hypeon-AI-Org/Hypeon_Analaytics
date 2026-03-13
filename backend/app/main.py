"""
FastAPI backend: enterprise multi-tenant, insights (paginated/top), review/apply, copilot Q&A only.
All queries scoped by organization_id; no cross-client leakage.
Copilot uses Gemini when GEMINI_API_KEY or Vertex AI is configured.
No decision engine; analytics + attribution + Copilot only.
"""
from __future__ import annotations

try:
    from pathlib import Path
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parents[2]  # repo root when main.py is backend/app/main.py
    _env_file = _root / ".env"
    loaded = load_dotenv(_env_file, override=True)
    if not loaded and Path.cwd() != _root:
        loaded = load_dotenv(Path.cwd() / ".env", override=True)
    # When running from backend/, always try parent (repo root) so .env at repo root is found
    if Path.cwd().name == "backend":
        loaded = load_dotenv(Path.cwd().parent / ".env", override=True) or loaded
except Exception as _e:
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).warning("Could not load .env: %s", _e)

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
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
from .auth import (
    get_organization,
    get_organization_id,
    get_org_projects_flat,
    get_role_from_token as auth_get_role,
    get_user_id,
    init_firebase,
    is_dev_key_allowed,
    parse_org_projects,
    prefetch_firebase_public_keys,
    prefetch_firestore_connection,
)
from .config_loader import get
from .copilot_synthesizer import (
    set_llm_client,
    synthesize as copilot_synthesize,
    prepare_copilot_prompt,
    _parse_llm_response,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: wire Claude or Gemini for Copilot. No analytics cache; Copilot queries hypeon_marts directly."""
    try:
        import os
        _has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        _has_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        logger.info("Copilot env: ANTHROPIC_API_KEY=%s GEMINI/GOOGLE_API_KEY=%s", "set" if _has_anthropic else "not set", "set" if _has_gemini else "not set")
        from .llm_claude import is_claude_configured, make_claude_copilot_client
        from .llm_gemini import is_gemini_configured, make_gemini_copilot_client
        if is_claude_configured():
            set_llm_client(make_claude_copilot_client())
            logger.info("Copilot LLM: Claude%s", " | Gemini as fallback" if is_gemini_configured() else "")
        elif is_gemini_configured():
            set_llm_client(make_gemini_copilot_client())
            logger.info("Copilot LLM: Gemini")
        else:
            logger.warning("Copilot: no LLM configured. Set ANTHROPIC_API_KEY or GEMINI_API_KEY for chat.")
    except Exception as e:
        logger.warning("Copilot LLM setup failed: %s", e, exc_info=True)
    import os
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        os.environ["GOOGLE_CLOUD_PROJECT"] = get_bq_project()
    # FIREBASE_PROJECT_ID must be set in production via env; no hardcoded fallback
    try:
        init_firebase()
        prefetch_firebase_public_keys()
        prefetch_firestore_connection()
    except Exception as e:
        logger.warning("Firebase init: %s", e)
    # Eagerly resolve session store so Firestore vs in-memory is fixed at startup
    try:
        from .copilot.session_memory import get_session_store
        get_session_store()
    except Exception as e:
        logger.debug("Session store init: %s", e)
    logger.info("Request logging active: every API request will be logged (METHOD path -> status | duration)")
    _api_key = get_api_key()
    logger.info("API_KEY (X-API-Key auth for local dev): %s", "set" if (_api_key and _api_key.strip()) else "not set")
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

# Copilot rate limit: 20 req/min per user
from .middleware.rate_limit import CopilotRateLimitMiddleware
app.add_middleware(CopilotRateLimitMiddleware)

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

# Dashboard API (cache; business-overview, campaign-performance, funnel)
try:
    from .api.dashboard import router as dashboard_router
    app.include_router(dashboard_router, prefix="/api/v1")
except ImportError:
    pass

# Analysis API (queries BigQuery for in-depth breakdowns; optional)
try:
    from .api.analysis import router as analysis_router
    app.include_router(analysis_router, prefix="/api/v1")
except ImportError:
    pass

# Dynamic Dashboard API (schema-agnostic: datasets, tables, preview, aggregate, time-series)
try:
    from .api.dynamic_dashboard import router as dynamic_dashboard_router
    app.include_router(dynamic_dashboard_router, prefix="/api/v1")
except ImportError:
    pass


# ----- Auth and tenant context (must be before routes that use them) -----
# get_organization_id and get_role_from_token imported from .auth (Firebase + Firestore when Bearer present)

def get_workspace_id(request: Request) -> Optional[str]:
    return request.headers.get("X-Workspace-Id") or None


def get_role_from_token(request: Request) -> str:
    """Role from Firebase user doc, or API key / Bearer / viewer fallback."""
    return auth_get_role(request, get_api_key)


# Dev key only when ENV is not production (see is_dev_key_allowed). Production must set API_KEY.
DEV_API_KEY = "dev-local-secret"


def _has_any_auth(request: Request) -> bool:
    """True if request has valid API key or Bearer token. In production, dev-local-secret is rejected."""
    api_key = get_api_key()
    req_key = (request.headers.get("X-API-Key") or "").strip().replace("\r", "")
    if api_key and req_key and (api_key.strip().replace("\r", "") == req_key):
        return True
    if req_key == DEV_API_KEY and is_dev_key_allowed(request):
        return True
    if (request.headers.get("Authorization") or "").strip().startswith("Bearer "):
        return True
    return False


def require_role(*allowed: str):
    def dep(request: Request):
        if not _has_any_auth(request):
            raise HTTPException(
                401,
                detail={"code": "UNAUTHORIZED", "message": "Authentication required. Use Bearer token (Firebase) or X-API-Key."},
            )
        role = get_role_from_token(request)
        if role not in allowed:
            raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Insufficient role"})
        return role
    return dep


def require_organization(request: Request) -> str:
    """Require non-empty organization_id from request (Firestore user or header). No fallback."""
    org = get_organization_id(request)
    if not org or not org.strip():
        raise HTTPException(
            400,
            detail={"code": "MISSING_ORGANIZATION", "message": "Organization context is required. Sign in with Firebase or send X-Organization-Id."},
        )
    return org.strip()


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


class CopilotSessionsDeleteBody(BaseModel):
    session_ids: list[str] = Field(default_factory=list, description="Session IDs to delete")


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
@app.get("/api/v1/me")
def get_me(
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
    org_id: str = Depends(require_organization),
):
    """Return current user's organization and dataset list from Firestore. Supports Option B: projects (bq_project + datasets per project)."""
    uid = get_user_id(request)
    org_doc = get_organization(org_id)
    if not org_doc:
        logger.info("User me | org_id=%s user_id=%s (no org doc in Firestore)", org_id, uid or "(none)")
        return {
            "organization_id": org_id,
            "name": None,
            "client_ids": [],
            "ad_channels": [],
            "projects": [],
        }
    # Option B: org has "projects" array (bq_project + datasets with bq_dataset, bq_location)
    projects_raw = parse_org_projects(org_doc)
    flat = get_org_projects_flat(org_doc)
    if flat:
        client_ids = [c["client_id"] for c in flat]
        ad_channels_list = [
            {
                "client_id": c["client_id"],
                "description": c.get("description", ""),
                "bq_project": c.get("bq_project"),
                "bq_dataset": c.get("bq_dataset"),
                "bq_location": c.get("bq_location"),
                "type": c.get("type"),
            }
            for c in flat
        ]
        # Raw Option B structure for clients that want project grouping
        projects_for_response = [
            {
                "bq_project": p.get("bq_project"),
                "datasets": [
                    {
                        "bq_dataset": d.get("bq_dataset"),
                        "bq_location": d.get("bq_location"),
                        "type": d.get("type"),
                    }
                    for d in (p.get("datasets") or [])
                ],
            }
            for p in projects_raw
        ]
        datasets_summary = [(p.get("bq_project"), d.get("bq_dataset")) for p in projects_raw for d in (p.get("datasets") or [])]
        logger.info(
            "User me | org_id=%s user_id=%s org_name=%s datasets=%s",
            org_id, uid or "(none)", org_doc.get("name"), datasets_summary,
        )
        return {
            "organization_id": org_id,
            "name": org_doc.get("name"),
            "client_ids": client_ids,
            "ad_channels": ad_channels_list,
            "projects": projects_for_response,
        }
    # Legacy: ad_channels or datasets (no projects)
    raw_channels = org_doc.get("ad_channels") or org_doc.get("datasets")
    client_ids = []
    ad_channels_list = []
    if isinstance(raw_channels, list):
        for ch in raw_channels:
            if isinstance(ch, dict) and ch.get("client_id") is not None:
                cid = int(ch["client_id"])
                client_ids.append(cid)
                ad_channels_list.append({"client_id": cid, "description": ch.get("description", "")})
    elif isinstance(raw_channels, dict):
        for k, v in raw_channels.items():
            try:
                cid = int(k)
            except (TypeError, ValueError):
                continue
            client_ids.append(cid)
            desc = v.get("description", str(v)) if isinstance(v, dict) else str(v)
            ad_channels_list.append({"client_id": cid, "description": desc})
    if not client_ids:
        client_ids = [1]
        ad_channels_list = [{"client_id": 1, "description": "Default"}]
    return {
        "organization_id": org_id,
        "name": org_doc.get("name"),
        "client_ids": client_ids,
        "ad_channels": ad_channels_list,
        "projects": [],
    }


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
    top_n: Optional[int] = Query(5, ge=1, le=50),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Top N actionable insights per client (default from config)."""
    org = get_organization_id(request)
    n = top_n or get("top_insights_per_client", 5)
    try:
        items = _top_insights_scoped(org, client_id, n)
    except Exception as e:
        logger.warning("insights/top failed (org=%s): %s", org, e)
        items = []
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
    try:
        _update_insight_status(insight_id, org, body.status, None)
        return {"ok": True, "insight_id": insight_id, "status": body.status}
    except Exception as e:
        logger.exception("insight_review failed | insight_id=%s org=%s error=%s", insight_id, org, str(e)[:300])
        raise


@app.post("/insights/{insight_id}/apply")
def insight_apply(
    insight_id: str,
    body: InsightApplyBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst")),
):
    """Mark insight as applied (status only; no decision store)."""
    org = get_organization_id(request)
    try:
        from .clients.bigquery import get_insight_by_id
        insight = get_insight_by_id(insight_id, org)
        if not insight:
            api_error("NOT_FOUND", "Insight not found", 404)
        _update_insight_status(insight_id, org, "applied", body.applied_by)
        from .audit_logger import log_decision_applied
        log_decision_applied(org, insight_id, body.applied_by)
        return {"ok": True, "insight_id": insight_id, "status": "applied"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("insight_apply failed | insight_id=%s org=%s error=%s", insight_id, org, str(e)[:300])
        raise


def _copilot_stream_gen(insight_id: str, org: str):
    """Generator yielding SSE events: phase loading | generating | chunk | done. Any exception yields error phase (no 500)."""
    def emit(ev: dict) -> str:
        return "data: " + json.dumps(ev) + "\n\n"

    try:
        yield emit({"phase": "loading", "message": "Accessing insights & metrics…"})
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
        out["provenance"] = out.get("provenance") or "analytics_insights, supporting_metrics_snapshot"
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
    """Synthesized explanation from grounded sources only (insights + snapshot)."""
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
def _copilot_safe_response(out: dict) -> JSONResponse:
    """Build a 200 JSONResponse from copilot output; ensure all values are JSON-serializable."""
    answer = str(out.get("answer") or out.get("text") or "")
    text = str(out.get("text") or out.get("answer") or "")
    raw_data = out.get("data")
    if not isinstance(raw_data, list):
        raw_data = []
    data = []
    for r in raw_data:
        if not isinstance(r, dict):
            continue
        row = {}
        for k, v in r.items():
            row[k] = v.isoformat() if hasattr(v, "isoformat") else v
        data.append(row)
    session_id = str(out.get("session_id") or "")
    return JSONResponse(
        status_code=200,
        content={"answer": answer, "text": text, "data": data, "session_id": session_id},
    )


@app.post("/api/v1/copilot/chat")
def copilot_chat(
    body: CopilotChatBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Chat: every query is handled by the LLM with tools. Always returns 200 (never 500)."""
    import uuid
    fallback_answer = (
        "I'm having trouble right now. Please try again, or ask e.g. \"Views count of item FT05B from Google\". "
        "If this persists, check that ANTHROPIC_API_KEY or GEMINI_API_KEY is set and that the analytics schema is available."
    )
    try:
        sid = str((body.session_id or uuid.uuid4()) if body else uuid.uuid4())
    except Exception:
        sid = str(uuid.uuid4())
    default_fail = {"answer": fallback_answer, "data": [], "text": fallback_answer, "session_id": sid}

    try:
        org = get_organization_id(request)
        uid = get_user_id(request)
        logger.info("Copilot chat | org=%s user_id=%s session_id=%s", org, uid or "(none)", getattr(body, "session_id", None) or "(new)")
        from .copilot.chat_handler import chat
        msg = (getattr(body, "message", None) or "").strip()
        if not msg:
            return _copilot_safe_response({"answer": "Please type a message to get a response.", "data": [], "text": "Please type a message to get a response.", "session_id": sid})
        out = chat(org, msg, session_id=sid, client_id=getattr(body, "client_id", None), user_id=uid)
        text = (out.get("text") or out.get("answer") or "").strip()
        if text and ("couldn't complete" in text.lower() or "couldnt complete" in text.lower()):
            fallback = "I'm having trouble right now. Please try again in a moment, or ask something like \"Views count of item FT05B from Google\"."
            out = {**out, "text": fallback, "answer": fallback, "data": out.get("data") or []}
        return _copilot_safe_response(out)
    except Exception as e:
        logger.exception("Copilot chat failed | session_id=%s error=%s", sid, str(e)[:200])
        try:
            msg = (getattr(body, "message", None) or "").strip().lower()
            if msg in ("hi", "hello", "hey", "howdy", "hi there", "hello there", "yo"):
                return _copilot_safe_response({
                    "answer": "Hi! How can I help with your marketing analytics today? Ask about views, campaigns, traffic, or item performance.",
                    "data": [],
                    "text": "Hi! How can I help with your marketing analytics today? Ask about views, campaigns, traffic, or item performance.",
                    "session_id": sid,
                })
        except Exception:
            pass
        return _copilot_safe_response({**default_fail, "session_id": sid})


def _copilot_chat_stream_gen(
    org: str, message: str, session_id: Optional[str], client_id: Optional[int], user_id: Optional[str] = None
):
    """Yield SSE lines from chat_stream. Each event: data: <json>\\n\\n. user_id scopes sessions to the logged-in user."""
    from .copilot.chat_handler import chat_stream
    for ev in chat_stream(org, message, session_id=session_id, client_id=client_id, user_id=user_id):
        yield "data: " + json.dumps(ev) + "\n\n"


@app.post("/api/v1/copilot/chat/stream")
def copilot_chat_stream(
    body: CopilotChatBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Stream copilot chat with status phases (analyzing, discovering, generating_sql, running_query, formatting) then done or error. Sessions scoped by user."""
    org = get_organization_id(request)
    uid = get_user_id(request)
    msg = (getattr(body, "message", None) or "").strip()
    sid = getattr(body, "session_id", None)
    cid = getattr(body, "client_id", None)
    return StreamingResponse(
        _copilot_chat_stream_gen(org, msg, sid, cid, uid),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/v1/copilot/chat/history")
def copilot_chat_history(
    request: Request,
    session_id: str = Query(..., description="Session to load"),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Return message history for a chat session (for restoring UI after refresh). Scoped by user so they see only their chats."""
    org = get_organization_id(request)
    uid = get_user_id(request)
    from .copilot.session_memory import get_session_store
    store = get_session_store()
    messages = store.get_messages(org, session_id, user_id=uid)
    return {"session_id": session_id, "messages": messages}


@app.post("/api/v1/copilot/refresh-schema")
def copilot_refresh_schema(
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """On init/login: if schema cache is missing or older than 10h, run full refresh (discover all datasets + LLM summary) and save. If cache exists and is under 10h old, skip refresh. Call after login so Copilot can answer questions faster."""
    org = get_organization_id(request)
    uid = get_user_id(request)
    from .auth.firestore_user import get_org_bq_context
    from .copilot.schema_cache_firestore import (
        get_schema_cache_updated_at,
        REFRESH_IF_OLDER_THAN_SECONDS,
        set_cached_schema,
    )
    ctx = get_org_bq_context(org)
    if not ctx or not ctx.get("bq_project"):
        return JSONResponse(
            status_code=400,
            content={"error": "Datasets are not configured for your organization. Configure BigQuery data sources in organization settings."},
        )
    # If cache exists and is fresh (< 10h), skip heavy refresh
    updated_at = get_schema_cache_updated_at(org)
    now = time.time()
    if updated_at is not None and (now - updated_at) < REFRESH_IF_OLDER_THAN_SECONDS:
        logger.info(
            "Copilot refresh-schema skipped (cache fresh) | org_id=%s user_id=%s age_hours=%.1f",
            org, uid or "(none)", (now - updated_at) / 3600,
        )
        return {
            "ok": True,
            "skipped": True,
            "reason": "cache_fresh",
            "updated_at": updated_at,
            "message": "Schema cache is under 10 hours old; no refresh needed.",
        }
    # No cache or older than 10h: run full refresh
    from .clients.bigquery import list_tables_for_discovery
    from .copilot.schema_summary import summarize_schema_with_llm
    tables = list_tables_for_discovery(organization_id=org)
    if not tables:
        return JSONResponse(status_code=200, content={"ok": True, "tables_count": 0, "message": "No tables found in configured datasets."})
    schema_summary = summarize_schema_with_llm(org, tables)
    written = set_cached_schema(org, ctx["bq_project"], tables, schema_summary=schema_summary)
    logger.info(
        "Copilot refresh-schema | org_id=%s user_id=%s tables=%d schema_summary=%s written=%s",
        org, uid or "(none)", len(tables), bool(schema_summary), written,
    )
    return {
        "ok": True,
        "tables_count": len(tables),
        "schema_summary_computed": schema_summary is not None,
        "updated_at": time.time() if written else None,
    }


@app.get("/api/v1/copilot/datasets")
def copilot_datasets(
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
    org: str = Depends(require_organization),
    include_tables: bool = Query(False, description="Run BQ discovery and return table list (slower)"),
):
    """
    Return which datasets (and optionally tables) the Copilot will use for this organization.
    Uses Firestore org config only. Use ?include_tables=true to run BQ discovery and return table list (slower).
    """
    from .auth.firestore_user import get_org_bq_context, get_org_all_dataset_configs
    ctx = get_org_bq_context(org)
    if not ctx or not ctx.get("bq_project"):
        return JSONResponse(
            status_code=200,
            content={
                "organization_id": org,
                "datasets": [],
                "tables_count": 0,
                "tables": [],
                "message": "Datasets are not configured for this organization.",
            },
        )
    configs = get_org_all_dataset_configs(org)
    datasets = [
        {"bq_project": c.get("bq_project"), "bq_dataset": c.get("bq_dataset"), "bq_location": c.get("bq_location") or "europe-north2"}
        for c in configs
    ]
    out = {"organization_id": org, "datasets": datasets, "tables_count": 0, "tables": []}
    if include_tables:
        from .clients.bigquery import list_tables_for_discovery
        tables = list_tables_for_discovery(organization_id=org)
        out["tables_count"] = len(tables)
        out["tables"] = [
            {"project": t.get("project"), "dataset": t.get("dataset"), "table_name": t.get("table_name"), "column_count": len(t.get("columns") or [])}
            for t in tables
        ]
    return out


@app.get("/api/v1/copilot/store-info")
def copilot_store_info(
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
    org: str = Depends(require_organization),
):
    """Return which session store is used, current org, and user_id (for diagnostics). Sessions are scoped by user."""
    import os
    from .copilot.session_memory import get_session_store
    store = get_session_store()
    kind = "firestore" if type(store).__name__ == "FirestoreSessionStore" else "memory"
    db_id = os.environ.get("FIRESTORE_DATABASE_ID") if kind == "firestore" else None
    uid = get_user_id(request)
    return {"store": kind, "database_id": db_id, "organization_id": org, "user_id": uid}


def _fetch_copilot_sessions(org: str, uid: Optional[str]) -> list:
    """Run store init + get_sessions in thread so slow Firestore is capped by timeout."""
    from .copilot.session_memory import get_session_store
    store = get_session_store()
    return store.get_sessions(org, uid)


@app.get("/api/v1/copilot/sessions")
def copilot_sessions(
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
    org: str = Depends(require_organization),
):
    """Return list of chat sessions for the current user (title, session_id, updated_at). User-scoped so they see their chats on re-login."""
    uid = get_user_id(request)
    logger.info("Copilot GET /sessions start org=%s (timeout=12s)", org)
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_fetch_copilot_sessions, org, uid)
            sessions = fut.result(timeout=12)
    except FuturesTimeoutError:
        logger.warning("Copilot GET /sessions timed out for org=%s user_id=%s", org, uid or "(none)")
        sessions = []
    except Exception as e:
        try:
            from google.auth.exceptions import RefreshError
            if isinstance(e, RefreshError):
                logger.warning(
                    "Copilot GET /sessions: Google credentials need reauth (org=%s). Run: gcloud auth application-default login",
                    org,
                )
        except ImportError:
            pass
        logger.warning("Copilot GET /sessions failed for org=%s: %s", org, e)
        sessions = []
    logger.info("Copilot GET /sessions org=%s user_id=%s count=%d", org, uid or "(none)", len(sessions))
    return {"sessions": sessions}


@app.post("/api/v1/copilot/sessions/delete")
def copilot_sessions_delete(
    body: CopilotSessionsDeleteBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
    org: str = Depends(require_organization),
):
    """Delete one or more chat sessions for the current user. Returns deleted count."""
    uid = get_user_id(request)
    from .copilot.session_memory import get_session_store
    store = get_session_store()
    deleted = 0
    for sid in body.session_ids or []:
        if sid and store.clear_session(org, sid, user_id=uid):
            deleted += 1
    logger.info("Copilot POST /sessions/delete org=%s user_id=%s requested=%d deleted=%d", org, uid or "(none)", len(body.session_ids or []), deleted)
    return {"deleted": deleted, "session_ids": body.session_ids or []}


@app.get("/health")
def health():
    """Liveness. Copilot queries hypeon_marts directly; no cache dependency."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: confirms server is up and auth timeouts are active (for debugging)."""
    return {"status": "ok", "version": "2.0.0", "auth_timeouts": True}


@app.get("/api/v1/debug-auth")
def debug_auth(request: Request):
    """No-auth debug: whether API_KEY is set and if request X-API-Key matches (for local dev)."""
    api_key = get_api_key()
    req_key = (request.headers.get("X-API-Key") or "").strip()
    return {
        "api_key_configured": bool(api_key),
        "request_has_api_key": bool(req_key),
        "key_match": bool(api_key and req_key and api_key == req_key),
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
    try:
        _update_insight_status(body.insight_id, org, body.status, body.user_id)
        return {"ok": True, "insight_id": body.insight_id, "status": body.status}
    except Exception as e:
        logger.exception(
            "recommendations_apply_legacy failed | insight_id=%s org=%s error=%s",
            body.insight_id, org, str(e)[:300],
        )
        raise
