"""
Structured logging for agent runs and API. Enterprise: organization_id, agent_name, insights_generated, runtime, errors.
"""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Optional

_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger("hypeon.analytics")
        if not _logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("%(message)s"))
            _logger.addHandler(h)
            _logger.setLevel(getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO))
    return _logger


def _structured(level: str, message: str, **kwargs: Any) -> None:
    payload = {"level": level, "message": message, **kwargs}
    get_logger().log(getattr(logging, level.upper(), logging.INFO), json.dumps(payload, default=str))


def log_agent_run(
    organization_id: str,
    agent_name: str,
    insights_generated: int,
    runtime_seconds: float,
    client_id: Optional[int] = None,
    workspace_id: Optional[str] = None,
    errors: Optional[list[str]] = None,
    **extra: Any,
) -> None:
    _structured(
        "INFO" if not errors else "ERROR",
        "agent_run",
        organization_id=organization_id,
        agent_name=agent_name,
        insights_generated=insights_generated,
        runtime_seconds=runtime_seconds,
        client_id=client_id,
        workspace_id=workspace_id,
        errors=errors or [],
        **extra,
    )


@contextmanager
def agent_run_context(organization_id: str, agent_name: str, client_id: Optional[int] = None, workspace_id: Optional[str] = None):
    start = time.perf_counter()
    errors: list[str] = []
    try:
        yield errors
    except Exception as e:
        errors.append(str(e))
        raise
    finally:
        log_agent_run(
            organization_id=organization_id,
            agent_name=agent_name,
            insights_generated=0,
            runtime_seconds=time.perf_counter() - start,
            client_id=client_id,
            workspace_id=workspace_id,
            errors=errors if errors else None,
        )
