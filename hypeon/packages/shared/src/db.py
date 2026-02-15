"""Database engine and session factory; FastAPI dependency."""
import os
from contextlib import contextmanager
from typing import Generator

from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from packages.shared.src import models  # noqa: F401 - ensure tables registered

_engine = None

# Default to Docker Postgres on 5433 (avoids conflict with local Postgres on 5432)
_DEFAULT_URL = "postgresql://postgres:postgres@localhost:5433/hypeon"


def get_engine():
    """Create or return the global engine. Reads DATABASE_URL when first called (after .env may be loaded)."""
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", _DEFAULT_URL)
        # Use 127.0.0.1:5433 for local DB (Docker Postgres). Avoids localhost→::1 and port 5432 auth failure.
        if "localhost" in url or "127.0.0.1" in url:
            url = url.replace(":5432", ":5433").replace("localhost", "127.0.0.1")
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            echo=os.environ.get("SQL_ECHO", "").lower() in ("1", "true"),
        )
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for a DB session."""
    engine = get_engine()
    with Session(engine) as session:
        yield session


def get_session_fastapi() -> Generator[Session, None, None]:
    """FastAPI dependency: yield session then close."""
    with get_session() as session:
        yield session


def init_db_for_tests():
    """In-memory SQLite engine for tests."""
    from sqlmodel import create_engine

    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
