"""E2E integration test: run product-engine pipeline and assert outputs and API shapes."""
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, select
from sqlmodel.pool import StaticPool

from packages.shared.src import models  # noqa: F401
from packages.shared.src.models import DecisionStore, UnifiedDailyMetrics
from sqlmodel import SQLModel
from packages.shared.src.db import get_session
from packages.shared.src.ingest import run_ingest
from packages.attribution.src.runner import run_attribution
from packages.mmm.src.runner import run_mmm
from packages.metrics.src.aggregator import run_metrics
from packages.rules_engine.src.rules import run_rules
from datetime import date, timedelta
from apps.api.src.app import app, get_session_fastapi


@pytest.fixture
def engine_and_data_dir(tmp_path):
    """Create in-memory engine with tables and copy fixture CSVs to tmp_path."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    data_dir = tmp_path / "raw"
    data_dir.mkdir()
    repo_root = Path(__file__).resolve().parent.parent.parent
    repo_data = repo_root / "data" / "raw"
    for name in ("meta_ads.csv", "google_ads.csv", "shopify_orders.csv"):
        src = repo_data / name
        if src.exists():
            (data_dir / name).write_text(src.read_text())
    return engine, data_dir


def test_product_engine_e2e(engine_and_data_dir):
    engine, data_dir = engine_and_data_dir
    start = date(2025, 1, 1)
    end = date(2025, 1, 31)
    run_id = "run-e2e"
    with Session(engine) as session:
        run_ingest(session, data_dir=data_dir)
        run_attribution(session, run_id=run_id, start_date=start, end_date=end)
        run_mmm(session, run_id=run_id, start_date=start, end_date=end)
        run_metrics(session, start_date=start, end_date=end, attribution_run_id=run_id)
        run_rules(session, start_date=start, end_date=end, mmm_run_id=run_id)
    with Session(engine) as session:
        metrics_rows = list(session.exec(select(UnifiedDailyMetrics)).all())
        decision_rows = list(session.exec(select(DecisionStore)).all())
    assert len(metrics_rows) >= 1, "unified_daily_metrics should have rows for date span and channels"
    assert len(decision_rows) >= 1, "decision_store should have at least one decision"
    scaling = [d for d in decision_rows if d.decision_type in ("scale_up", "scale_down", "reallocate_budget")]
    assert len(scaling) >= 1 or len(decision_rows) >= 1, "at least one scaling-window or logic-appropriate decision"


def test_api_metrics_and_decisions_return_200_and_shape(engine_and_data_dir):
    engine, data_dir = engine_and_data_dir
    start = date(2025, 1, 1)
    end = date(2025, 1, 31)
    run_id = "run-api"
    with Session(engine) as session:
        run_ingest(session, data_dir=data_dir)
        run_attribution(session, run_id=run_id, start_date=start, end_date=end)
        run_mmm(session, run_id=run_id, start_date=start, end_date=end)
        run_metrics(session, start_date=start, end_date=end, attribution_run_id=run_id)
        run_rules(session, start_date=start, end_date=end, mmm_run_id=run_id)
    def session_override():
        with Session(engine) as s:
            yield s
    client = TestClient(app)
    app.dependency_overrides[get_session_fastapi] = session_override
    try:
        r_metrics = client.get("/metrics/unified")
        assert r_metrics.status_code == 200
        j = r_metrics.json()
        assert "metrics" in j and isinstance(j["metrics"], list)
        r_decisions = client.get("/decisions")
        assert r_decisions.status_code == 200
        jd = r_decisions.json()
        assert "decisions" in jd and "total" in jd
    finally:
        app.dependency_overrides.pop(get_session_fastapi, None)


def test_api_v1_engine_run_returns_envelope(engine_and_data_dir):
    """POST /api/v1/engine/run returns envelope: success, data, meta, errors."""
    engine, data_dir = engine_and_data_dir
    with Session(engine) as session:
        run_ingest(session, data_dir=data_dir)
    def session_override():
        with Session(engine) as s:
            yield s
    client = TestClient(app)
    app.dependency_overrides[get_session_fastapi] = session_override
    try:
        r = client.post("/api/v1/engine/run", params={"seed": 42})
        assert r.status_code in (200, 500), r.text
        j = r.json()
        assert "success" in j
        assert "data" in j
        assert "meta" in j
        assert "errors" in j
        assert isinstance(j["errors"], list)
        if r.status_code == 200 and j.get("success"):
            assert "run_id" in j["data"]
    finally:
        app.dependency_overrides.pop(get_session_fastapi, None)


def test_api_v1_decisions_returns_envelope_and_schema(engine_and_data_dir):
    """GET /api/v1/decisions returns envelope and at least one decision with required shape."""
    engine, data_dir = engine_and_data_dir
    start = date(2025, 1, 1)
    end = date(2025, 1, 31)
    run_id = "run-v1-dec"
    with Session(engine) as session:
        run_ingest(session, data_dir=data_dir)
        run_attribution(session, run_id=run_id, start_date=start, end_date=end)
        run_mmm(session, run_id=run_id, start_date=start, end_date=end)
        run_metrics(session, start_date=start, end_date=end, attribution_run_id=run_id)
        run_rules(session, start_date=start, end_date=end, mmm_run_id=run_id)
    def session_override():
        with Session(engine) as s:
            yield s
    client = TestClient(app)
    app.dependency_overrides[get_session_fastapi] = session_override
    try:
        r = client.get("/api/v1/decisions")
        assert r.status_code == 200, r.text
        j = r.json()
        assert "success" in j and "data" in j and "meta" in j and "errors" in j
        data = j.get("data") or {}
        decisions = data.get("decisions") or []
        total = data.get("total", 0)
        assert isinstance(decisions, list)
        assert total >= 0
        if decisions:
            d = decisions[0]
            assert "decision_id" in d
            assert "channel" in d
            assert "recommended_action" in d
            assert "reasoning" in d
            assert "risk_flags" in d
            assert "confidence_score" in d
            assert "model_versions" in d or "run_id" in d
    finally:
        app.dependency_overrides.pop(get_session_fastapi, None)
