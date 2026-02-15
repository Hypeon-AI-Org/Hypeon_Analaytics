"""API tests (unit: override DB to in-memory)."""
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from apps.api.src.app import app, get_session_fastapi
from packages.shared.src import models  # noqa: F401
from sqlmodel import SQLModel


@contextmanager
def _mem_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_run_pipeline():
    def override():
        with _mem_session() as s:
            yield s
    client = TestClient(app)
    app.dependency_overrides[get_session_fastapi] = override
    try:
        r = client.post("/run?seed=42")
        assert r.status_code == 202
        data = r.json()
        assert data["run_id"] == "run-42"
        assert data["status"] == "accepted"
    finally:
        app.dependency_overrides.pop(get_session_fastapi, None)


def test_metrics_unified_shape():
    def override():
        with _mem_session() as s:
            yield s
    client = TestClient(app)
    app.dependency_overrides[get_session_fastapi] = override
    try:
        r = client.get("/metrics/unified")
        assert r.status_code == 200
        j = r.json()
        assert "metrics" in j
        assert isinstance(j["metrics"], list)
    finally:
        app.dependency_overrides.pop(get_session_fastapi, None)


def test_decisions_shape():
    def override():
        with _mem_session() as s:
            yield s
    client = TestClient(app)
    app.dependency_overrides[get_session_fastapi] = override
    try:
        r = client.get("/decisions")
        assert r.status_code == 200
        j = r.json()
        assert "decisions" in j and "total" in j
    finally:
        app.dependency_overrides.pop(get_session_fastapi, None)
