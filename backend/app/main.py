"""
FastAPI backend: enterprise multi-tenant, insights (paginated/top), review/apply, decision history, copilot.
All queries scoped by organization_id; no cross-client leakage.
Copilot uses Gemini when GEMINI_API_KEY or Vertex AI is configured.
"""
from __future__ import annotations

try:
    from pathlib import Path
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parents[2]
    load_dotenv(_root / ".env")
except Exception:
    pass

import json
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
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
    """On startup: wire Gemini as Copilot LLM when configured; warm analytics cache."""
    try:
        from .llm_gemini import is_gemini_configured, make_gemini_copilot_client
        if is_gemini_configured():
            set_llm_client(make_gemini_copilot_client())
    except Exception:
        pass  # keep default stub if Gemini not available
    # Cache warmup: populate analytics cache from BQ so first dashboard requests are fast
    try:
        from .refresh_analytics_cache import do_refresh
        do_refresh(organization_id="default", client_id=1)
    except Exception:
        pass
    yield


app = FastAPI(title="HypeOn Analytics V1 API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_cors_origins(), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Dashboard API (reads from analytics cache only; <300ms target)
from .api.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/api/v1")


@app.post("/api/v1/admin/refresh-cache")
def admin_refresh_cache(
    request: Request,
    _role: str = Depends(require_role("admin")),
):
    """Refresh analytics cache from BQ. Used by DAG or manual trigger. Requires admin."""
    org = get_organization_id(request)
    from .refresh_analytics_cache import do_refresh
    result = do_refresh(organization_id=org, client_id=1)
    return result


# ----- Auth and tenant context -----
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


class CopilotV1QueryBody(BaseModel):
    query: str
    client_id: Optional[int] = None
    session_id: Optional[str] = None
    insight_id: Optional[str] = None


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
    """Paginated insights scoped by organization."""
    org = get_organization_id(request)
    workspace = get_workspace_id(request)
    items = _list_insights_scoped(org, client_id, workspace, status, limit, offset)
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
    """Generator yielding SSE events: phase loading | generating | chunk | done."""
    def emit(ev: dict) -> str:
        return "data: " + json.dumps(ev) + "\n\n"

    yield emit({"phase": "loading", "message": "Accessing insights & decision history…"})
    prompt, err = prepare_copilot_prompt(insight_id, organization_id=org)
    if err is not None:
        yield emit({"phase": "error", "error": err.get("error", "Unknown error")})
        return

    yield emit({"phase": "generating", "message": "Generating analysis…"})
    try:
        from .llm_gemini import stream_gemini
        acc = []
        for chunk in stream_gemini(prompt):
            acc.append(chunk)
            yield emit({"phase": "chunk", "text": chunk})
        full = "".join(acc)
        out = _parse_llm_response(full)
        out["insight_id"] = insight_id
        out["provenance"] = out.get("provenance") or "analytics_insights, decision_history, supporting_metrics_snapshot"
        yield emit({"phase": "done", "data": out})
    except Exception as e:
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


# ----- V1 Copilot (free-form query, structured context, optional layout) -----
@app.post("/api/v1/copilot/query")
def copilot_v1_query(
    body: CopilotV1QueryBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Free-form Copilot: single context, mode routing, returns summary, top_drivers, recommended_actions, confidence, optional layout."""
    org = get_organization_id(request)
    from .copilot.copilot_facade import query_copilot
    out = query_copilot(
        body.query,
        org,
        client_id=body.client_id,
        session_id=body.session_id,
        insight_id=body.insight_id,
    )
    return out


def _copilot_v1_stream_gen(body: CopilotV1QueryBody, org: str):
    def emit(ev: dict) -> str:
        return "data: " + json.dumps(ev) + "\n\n"
    yield emit({"phase": "loading", "message": "Building context…"})
    from .copilot.copilot_facade import query_copilot
    out = query_copilot(body.query, org, client_id=body.client_id, session_id=body.session_id, insight_id=body.insight_id)
    yield emit({"phase": "done", "data": out})


@app.post("/api/v1/copilot/stream")
def copilot_v1_stream(
    body: CopilotV1QueryBody,
    request: Request,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Stream V1 Copilot response (SSE): loading then done with full structured data."""
    org = get_organization_id(request)
    return StreamingResponse(
        _copilot_v1_stream_gen(body, org),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    return {"status": "ok"}


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
