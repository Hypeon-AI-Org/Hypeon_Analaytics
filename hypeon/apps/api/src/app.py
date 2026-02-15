"""FastAPI app: health, metrics, decisions, POST /run pipeline, MMM status/results, copilot."""
from datetime import date, timedelta
from pathlib import Path

# Load .env so DATABASE_URL and GEMINI_* are set (try workspace root, then hypeon, then cwd)
from dotenv import load_dotenv
_app_dir = Path(__file__).resolve().parent
for _env_dir in [_app_dir.parent.parent.parent.parent, _app_dir.parent.parent.parent, Path.cwd()]:
    _env_file = _env_dir / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
        break

import json

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlmodel import Session, select

from packages.shared.src.db import get_engine, get_session_fastapi
from packages.shared.src.models import (
    CopilotMessage,
    CopilotSession,
    DecisionStore,
    MMMResults,
    UnifiedDailyMetrics,
)
from packages.shared.src.schemas import (
    AttributionMMMReportResponse,
    BudgetAllocationResponse,
    CopilotAskRequest,
    CopilotAskResponse,
    CopilotContextResponse,
    CopilotMessageRow,
    CopilotMessagesResponse,
    CopilotSessionListItem,
    CopilotSessionsResponse,
    DecisionRow,
    DecisionsResponse,
    MMMResultRow,
    MMMResultsResponse,
    MMMStatusResponse,
    RunTriggerResponse,
    SimulateRequest,
    SimulateResponse,
    UnifiedMetricRow,
    UnifiedMetricsResponse,
)
from packages.shared.src.dates import parse_date_range
from packages.shared.src.ingest import run_ingest
from packages.attribution.src.runner import run_attribution
from packages.mmm.src.runner import run_mmm
from packages.metrics.src.aggregator import run_metrics
from packages.rules_engine.src.rules import run_rules
from packages.mmm.src.optimizer import (
    allocate_budget_greedy,
    predicted_revenue,
)
from packages.mmm.src.simulator import projected_revenue_delta
from packages.metrics.src.attribution_mmm_report import build_attribution_mmm_report
from .copilot import generate_copilot_answer, get_copilot_context, stream_answer_with_gemini

app = FastAPI(title="HypeOn Product Engine API", version="1.0.0")


@app.on_event("startup")
def ensure_copilot_tables():
    """Create copilot_sessions and copilot_messages if missing (e.g. migration not run)."""
    engine = get_engine()
    for model in (CopilotSession, CopilotMessage):
        try:
            model.__table__.create(engine, checkfirst=True)
        except Exception:
            pass


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
def unhandled_exception_handler(request, exc):
    """Return 500 with error detail so frontend and logs show the real cause."""
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


def _current_spend_by_channel(session: Session, lookback_days: int = 30) -> dict:
    """Sum spend by channel over recent lookback from unified_daily_metrics."""
    start = date.today() - timedelta(days=lookback_days)
    end = date.today()
    stmt = select(UnifiedDailyMetrics).where(
        UnifiedDailyMetrics.date >= start,
        UnifiedDailyMetrics.date <= end,
    )
    rows = list(session.exec(stmt).all())
    by_ch: dict = {}
    for r in rows:
        by_ch[r.channel] = by_ch.get(r.channel, 0.0) + r.spend
    return by_ch or {"meta": 0.0, "google": 0.0}


def _latest_mmm_coefficients(session: Session) -> dict:
    """Latest MMM run coefficients by channel."""
    stmt = select(MMMResults).order_by(MMMResults.created_at.desc())
    rows = list(session.exec(stmt).all())
    if not rows:
        return {}
    rid = rows[0].run_id
    return {r.channel: r.coefficient for r in rows if r.run_id == rid}


@app.get("/health")
def health():
    """Liveness check."""
    return {"status": "ok"}


def _ensure_date(d) -> str:
    """Ensure date is JSON-serializable (ISO string)."""
    if hasattr(d, "isoformat"):
        return d.isoformat()
    if isinstance(d, str):
        return d
    return str(d)


@app.get("/metrics/unified")
def get_metrics_unified(
    session: Session = Depends(get_session_fastapi),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    channel: str | None = Query(None),
):
    """Query unified daily metrics (date range + optional channel filter)."""
    start, end = parse_date_range(start_date, end_date)
    stmt = select(UnifiedDailyMetrics).where(
        UnifiedDailyMetrics.date >= start,
        UnifiedDailyMetrics.date <= end,
    )
    if channel:
        stmt = stmt.where(UnifiedDailyMetrics.channel == channel)
    stmt = stmt.order_by(UnifiedDailyMetrics.date, UnifiedDailyMetrics.channel)
    rows = list(session.exec(stmt).all())
    # Build response with JSON-serializable types (dates as ISO strings for compatibility)
    metrics_data = [
        {
            "date": _ensure_date(r.date),
            "channel": str(r.channel),
            "spend": float(r.spend),
            "attributed_revenue": float(r.attributed_revenue),
            "roas": float(r.roas) if r.roas is not None else None,
            "mer": float(r.mer) if r.mer is not None else None,
            "cac": float(r.cac) if r.cac is not None else None,
            "revenue_new": float(r.revenue_new) if r.revenue_new is not None else None,
            "revenue_returning": float(r.revenue_returning) if r.revenue_returning is not None else None,
        }
        for r in rows
    ]
    return {
        "metrics": metrics_data,
        "start_date": _ensure_date(start),
        "end_date": _ensure_date(end),
    }


@app.get("/decisions", response_model=DecisionsResponse)
def list_decisions(
    session: Session = Depends(get_session_fastapi),
    status: str | None = Query(None, description="Filter by status"),
):
    """List decisions from decision_store; optional status filter."""
    stmt = select(DecisionStore)
    if status is not None:
        stmt = stmt.where(DecisionStore.status == status)
    stmt = stmt.order_by(DecisionStore.created_at.desc())
    rows = list(session.exec(stmt).all())
    return DecisionsResponse(
        decisions=[
            DecisionRow(
                decision_id=r.decision_id,
                created_at=r.created_at,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                decision_type=r.decision_type,
                reason_code=r.reason_code,
                explanation_text=r.explanation_text,
                projected_impact=r.projected_impact,
                confidence_score=r.confidence_score,
                status=r.status,
            )
            for r in rows
        ],
        total=len(rows),
    )


@app.get("/model/mmm/status", response_model=MMMStatusResponse)
def mmm_status(session: Session = Depends(get_session_fastapi)):
    """Last MMM run summary."""
    stmt = select(MMMResults).order_by(MMMResults.created_at.desc()).limit(1)
    r = session.exec(stmt).first()
    if not r:
        return MMMStatusResponse(status="no_runs")
    return MMMStatusResponse(
        last_run_id=r.run_id,
        last_run_at=r.created_at,
        status="completed",
    )


@app.get("/model/mmm/results", response_model=MMMResultsResponse)
def mmm_results(
    session: Session = Depends(get_session_fastapi),
    run_id: str | None = Query(None),
):
    """MMM results (optional run_id; else latest run)."""
    stmt = select(MMMResults).order_by(MMMResults.created_at.desc())
    if run_id:
        stmt = stmt.where(MMMResults.run_id == run_id)
    rows = list(session.exec(stmt).all())
    if not rows:
        return MMMResultsResponse(run_id=run_id, results=[])
    rid = rows[0].run_id
    by_run = [r for r in rows if r.run_id == rid]
    return MMMResultsResponse(
        run_id=rid,
        results=[
            MMMResultRow(
                run_id=r.run_id,
                created_at=r.created_at,
                channel=r.channel,
                coefficient=r.coefficient,
                goodness_of_fit_r2=r.goodness_of_fit_r2,
                model_version=r.model_version,
            )
            for r in by_run
        ],
    )


@app.post("/simulate", response_model=SimulateResponse)
def simulate(
    session: Session = Depends(get_session_fastapi),
    body: SimulateRequest = SimulateRequest(),
):
    """Projected revenue delta for given spend changes (e.g. meta +20%, google -10%)."""
    current = _current_spend_by_channel(session)
    spend_changes = {}
    if body.meta_spend_change is not None:
        spend_changes["meta"] = body.meta_spend_change
    if body.google_spend_change is not None:
        spend_changes["google"] = body.google_spend_change
    coefs = _latest_mmm_coefficients(session)
    if not coefs:
        return SimulateResponse(
            projected_revenue_delta=0.0,
            current_spend=current,
            new_spend=current,
        )
    delta = projected_revenue_delta(current, spend_changes, coefs)
    new_spend = {
        ch: current.get(ch, 0.0) * (1.0 + spend_changes.get(ch, 0.0))
        for ch in set(list(current.keys()) + list(spend_changes.keys()))
    }
    return SimulateResponse(
        projected_revenue_delta=round(delta, 2),
        current_spend=current,
        new_spend=new_spend,
    )


@app.get("/optimizer/budget", response_model=BudgetAllocationResponse)
def optimizer_budget(
    session: Session = Depends(get_session_fastapi),
    total_budget: float = Query(..., description="Total spend to allocate"),
):
    """Recommend channel allocation to maximize predicted revenue (greedy marginal ROAS)."""
    current = _current_spend_by_channel(session)
    coefs = _latest_mmm_coefficients(session)
    if not coefs:
        return BudgetAllocationResponse(
            total_budget=total_budget,
            recommended_allocation=current,
            current_spend=current,
            predicted_revenue_at_recommended=0.0,
        )
    recommended = allocate_budget_greedy(total_budget, coefs, current_spend=current)
    pred_rev = predicted_revenue(recommended, coefs)
    return BudgetAllocationResponse(
        total_budget=total_budget,
        recommended_allocation=recommended,
        current_spend=current,
        predicted_revenue_at_recommended=round(pred_rev, 2),
    )


@app.get("/report/attribution-mmm-comparison", response_model=AttributionMMMReportResponse)
def report_attribution_mmm(
    session: Session = Depends(get_session_fastapi),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """Compare MTA attribution share vs MMM contribution share; flag instability if they disagree heavily."""
    start, end = parse_date_range(start_date, end_date)
    report = build_attribution_mmm_report(session, start, end)
    return AttributionMMMReportResponse(
        channels=report["channels"],
        attribution_share=report["attribution_share"],
        mmm_share=report["mmm_share"],
        disagreement_score=report["disagreement_score"],
        instability_flagged=report["instability_flagged"],
    )


def _run_pipeline(
    session: Session,
    seed: int | None,
    data_dir: Path | None,
) -> str:
    """Execute ingest -> attribution -> mmm -> metrics -> rules; return run_id."""
    import random
    if seed is not None:
        random.seed(seed)
    run_id = f"run-{seed if seed is not None else 'default'}"
    run_ingest(session, data_dir=data_dir)
    # Use 365-day lookback so sample data (e.g. Jan 2025) is included
    start = date.today() - timedelta(days=365)
    end = date.today()
    run_attribution(session, run_id=run_id, start_date=start, end_date=end)
    run_mmm(session, run_id=run_id, start_date=start, end_date=end)
    run_metrics(session, start_date=start, end_date=end, attribution_run_id=run_id)
    run_rules(session, start_date=start, end_date=end, mmm_run_id=run_id)
    return run_id


# ----- Copilot (for founders / non-technical) -----


@app.get("/copilot/context", response_model=CopilotContextResponse)
def copilot_context(
    session: Session = Depends(get_session_fastapi),
    lookback_days: int = Query(90, ge=7, le=365),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """Summary of current data used by Copilot (dashboard-aligned). Optional start_date/end_date."""
    ctx = get_copilot_context(
        session, lookback_days=lookback_days, start_date=start_date, end_date=end_date
    )
    report = ctx.get("attribution_mmm_report") or {}
    return CopilotContextResponse(
        start_date=ctx.get("start_date"),
        end_date=ctx.get("end_date"),
        lookback_days=ctx.get("lookback_days", 90),
        channels=ctx.get("channels", []),
        total_spend=ctx.get("total_spend", 0),
        total_revenue=ctx.get("total_revenue", 0),
        roas_overall=ctx.get("roas_overall", 0),
        decisions_total=ctx.get("decisions_total", 0),
        decisions_pending=ctx.get("decisions_pending", 0),
        mmm_last_run_id=ctx.get("mmm_last_run_id"),
        instability_flagged=report.get("instability_flagged", False),
    )


@app.get("/copilot/sessions", response_model=CopilotSessionsResponse)
def copilot_list_sessions(session: Session = Depends(get_session_fastapi)):
    """List all copilot sessions (newest first)."""
    stmt = select(CopilotSession).order_by(CopilotSession.created_at.desc()).limit(100)
    rows = list(session.exec(stmt).all())
    return CopilotSessionsResponse(
        sessions=[
            CopilotSessionListItem(id=r.id, title=r.title, created_at=r.created_at)
            for r in rows
        ]
    )


@app.post("/copilot/sessions", response_model=CopilotSessionListItem)
def copilot_create_session(session: Session = Depends(get_session_fastapi)):
    """Create a new copilot session."""
    s = CopilotSession()
    session.add(s)
    session.commit()
    session.refresh(s)
    return CopilotSessionListItem(id=s.id, title=s.title, created_at=s.created_at)


@app.get("/copilot/sessions/{session_id:int}/messages", response_model=CopilotMessagesResponse)
def copilot_get_messages(
    session_id: int,
    session: Session = Depends(get_session_fastapi),
):
    """Get all messages in a session (chronological)."""
    stmt = select(CopilotMessage).where(CopilotMessage.session_id == session_id).order_by(CopilotMessage.created_at)
    rows = list(session.exec(stmt).all())
    return CopilotMessagesResponse(
        session_id=session_id,
        messages=[
            CopilotMessageRow(id=m.id, role=m.role, content=m.content, created_at=m.created_at)
            for m in rows
        ],
    )


def _copilot_ensure_session(session: Session, session_id: int | None):
    """Create a session if session_id is None; return session id."""
    if session_id is not None:
        return session_id
    s = CopilotSession()
    session.add(s)
    session.commit()
    session.refresh(s)
    return s.id


@app.post("/copilot/ask", response_model=CopilotAskResponse)
def copilot_ask(
    session: Session = Depends(get_session_fastapi),
    body: CopilotAskRequest = CopilotAskRequest(question=""),
):
    """Answer a natural-language question using dashboard data. Optionally save to a session."""
    question = (body.question or "").strip() or "How are we doing?"
    sid = body.session_id if body.session_id is not None else _copilot_ensure_session(session, None)
    answer, sources = generate_copilot_answer(session, question)
    # Persist to session
    user_msg = CopilotMessage(session_id=sid, role="user", content=question)
    session.add(user_msg)
    session.commit()
    session.refresh(user_msg)
    assistant_msg = CopilotMessage(session_id=sid, role="assistant", content=answer)
    session.add(assistant_msg)
    session.commit()
    session.refresh(assistant_msg)
    # Optionally set session title from first question
    s = session.get(CopilotSession, sid)
    if s and not s.title:
        s.title = (question[:50] + "…") if len(question) > 50 else question
        session.add(s)
        session.commit()
    return CopilotAskResponse(
        answer=answer, sources=sources, session_id=sid, message_id=assistant_msg.id
    )


@app.post("/copilot/ask/stream")
def copilot_ask_stream(
    session: Session = Depends(get_session_fastapi),
    body: CopilotAskRequest = CopilotAskRequest(question=""),
):
    """Stream answer as SSE. Optionally save to session when done."""
    question = (body.question or "").strip() or "How are we doing?"
    sid = body.session_id if body.session_id is not None else _copilot_ensure_session(session, None)
    ctx = get_copilot_context(session, lookback_days=90)

    def event_stream():
        full = []
        sources_list = []
        # Save user message
        user_msg = CopilotMessage(session_id=sid, role="user", content=question)
        session.add(user_msg)
        session.commit()
        session.refresh(user_msg)
        for delta, sources in stream_answer_with_gemini(question, ctx):
            if delta:
                full.append(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"
            if sources is not None:
                sources_list = sources
                yield f"data: {json.dumps({'done': True, 'sources': sources, 'answer': ''.join(full)})}\n\n"
        # Persist assistant message
        answer_text = "".join(full)
        assistant_msg = CopilotMessage(session_id=sid, role="assistant", content=answer_text)
        session.add(assistant_msg)
        session.commit()
        session.refresh(assistant_msg)
        s = session.get(CopilotSession, sid)
        if s and not s.title:
            s.title = (question[:50] + "…") if len(question) > 50 else question
            session.add(s)
            session.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _default_data_dir() -> Path:
    """Resolve data/raw from repo root (hypeon), regardless of process cwd."""
    # app.py lives at hypeon/apps/api/src/app.py -> repo root is 4 levels up
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    return repo_root / "data" / "raw"


@app.post("/run", response_model=RunTriggerResponse, status_code=202)
def trigger_run(
    session: Session = Depends(get_session_fastapi),
    seed: int | None = Query(None, description="Deterministic run seed"),
):
    """Trigger idempotent product-engine pipeline: ingest -> attribution -> mmm -> metrics -> rules."""
    data_dir = _default_data_dir()
    run_id = _run_pipeline(session, seed, data_dir)
    return RunTriggerResponse(run_id=run_id, status="accepted", message="Pipeline run triggered.")


@app.post("/run/sync", response_model=RunTriggerResponse)
def trigger_run_sync(
    session: Session = Depends(get_session_fastapi),
    seed: int | None = Query(None, description="Deterministic run seed"),
):
    """Run pipeline synchronously; returns when done (for UI 'Run pipeline' button)."""
    data_dir = _default_data_dir()
    run_id = _run_pipeline(session, seed, data_dir)
    return RunTriggerResponse(run_id=run_id, status="completed", message="Pipeline completed.")
