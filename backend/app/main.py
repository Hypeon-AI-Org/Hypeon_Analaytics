"""
FastAPI backend: insights, recommendations/apply, simulate_budget_shift, copilot_query.
JWT auth stub and role-based checks (admin, analyst, viewer).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_api_key, get_bq_project, get_analytics_dataset, get_cors_origins
from .copilot_synthesizer import synthesize as copilot_synthesize

app = FastAPI(title="HypeOn Analytics V1 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=get_cors_origins(), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ----- Auth stub -----
def get_role_from_token(request: Request) -> str:
    """Extract role from JWT or API key. Stub: default analyst."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        # In prod: decode JWT and read role claim
        return "analyst"
    if get_api_key() and request.headers.get("X-API-Key") == get_api_key():
        return "admin"
    return "viewer"


def require_role(*allowed: str):
    def dep(request: Request):
        role = get_role_from_token(request)
        if role not in allowed:
            raise HTTPException(403, "Insufficient role")
        return role
    return dep


# ----- Schemas -----
class InsightsQuery(BaseModel):
    client_id: Optional[int] = None
    status: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)


class RecommendationApplyBody(BaseModel):
    insight_id: str
    user_id: Optional[str] = None
    status: str = Field("applied", pattern="^(applied|rejected)$")


class SimulateBudgetShiftBody(BaseModel):
    client_id: int
    date: str  # YYYY-MM-DD
    from_campaign: str
    to_campaign: str
    amount: float = Field(..., gt=0)


class CopilotQueryBody(BaseModel):
    insight_id: str


# ----- BigQuery helpers -----
def _bq_client():
    from .clients.bigquery import get_client
    return get_client()


def _list_insights(client_id: Optional[int], status: Optional[str], limit: int) -> list[dict]:
    client = _bq_client()
    project = get_bq_project()
    dataset = get_analytics_dataset()
    where = []
    if client_id is not None:
        where.append(f"client_id = {client_id}")
    if status:
        where.append(f"status = '{status}'")
    where_s = " AND ".join(where) if where else "1=1"
    query = f"""
    SELECT insight_id, client_id, entity_type, entity_id, insight_type, summary, explanation,
           recommendation, expected_impact, confidence, evidence, detected_by, status, created_at, applied_at
    FROM `{project}.{dataset}.analytics_insights`
    WHERE {where_s}
    ORDER BY created_at DESC
    LIMIT {limit}
    """
    df = client.query(query).to_dataframe()
    if df.empty:
        return []
    return [dict(row) for _, row in df.iterrows()]


def _update_insight_status(insight_id: str, status: str, user_id: Optional[str]) -> None:
    client = _bq_client()
    project = get_bq_project()
    dataset = get_analytics_dataset()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    user = (user_id or "unknown").replace("'", "''")
    query = f"""
    UPDATE `{project}.{dataset}.analytics_insights`
    SET status = '{status}', applied_at = CURRENT_TIMESTAMP(), history = CONCAT(COALESCE(history, ''), '; applied_by={user} at {now}')
    WHERE insight_id = '{insight_id}'
    """
    client.query(query).result()


# ----- Endpoints -----
@app.get("/insights")
def get_insights(
    client_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Paginated insights from analytics_insights."""
    items = _list_insights(client_id, status, limit)
    # Serialize for JSON (datetime, etc.)
    out = []
    for r in items:
        d = {}
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
            elif isinstance(v, (list, tuple)) and v and hasattr(v[0], "_fields"):
                d[k] = [dict(x) for x in v]
            else:
                d[k] = v
        out.append(d)
    return {"items": out, "count": len(out)}


@app.post("/recommendations/apply")
def recommendations_apply(
    body: RecommendationApplyBody,
    _role: str = Depends(require_role("admin", "analyst")),
):
    """Mark insight as applied or rejected; write to decision history."""
    _update_insight_status(body.insight_id, body.status, body.user_id)
    return {"ok": True, "insight_id": body.insight_id, "status": body.status}


@app.post("/simulate_budget_shift")
def simulate_budget_shift(
    body: SimulateBudgetShiftBody,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Simulate moving budget between campaigns; returns low/median/high scenario."""
    from .simulation import simulate_budget_shift as run_sim
    result = run_sim(
        client_id=body.client_id,
        date_str=body.date,
        from_campaign=body.from_campaign,
        to_campaign=body.to_campaign,
        amount=body.amount,
    )
    return result


@app.post("/copilot_query")
def copilot_query(
    body: CopilotQueryBody,
    _role: str = Depends(require_role("admin", "analyst", "viewer")),
):
    """Return synthesized explanation for the given insight_id."""
    out = copilot_synthesize(insight_id=body.insight_id)
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out


@app.get("/health")
def health():
    return {"status": "ok"}
