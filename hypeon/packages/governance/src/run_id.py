"""Run ID generator for engine runs. Pure function; no global state."""
from uuid import uuid4


def generate_run_id() -> str:
    """
    Generate a unique run ID (UUID4).
    Deterministic only when seeded for tests (e.g. monkeypatch uuid4).
    """
    return str(uuid4())
