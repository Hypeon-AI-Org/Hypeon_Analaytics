"""
Full Audit Logging: track agent_runs, insight_generated, decision_applied, copilot_queries, user_actions.
Enterprise requirement.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from .config_loader import get

_AUDIT_TO_BQ = True


def _bq_audit(event_type: str, organization_id: str, entity_id: Optional[str], user_id: Optional[str], payload: dict) -> None:
    if not _AUDIT_TO_BQ:
        return
    try:
        from .clients.bigquery import insert_audit_log
        insert_audit_log(
            organization_id=organization_id,
            event_type=event_type,
            entity_id=entity_id,
            user_id=user_id,
            payload=json.dumps(payload, default=str),
        )
    except Exception:
        pass


def log_audit(
    event_type: str,
    organization_id: str,
    *,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **payload: Any,
) -> None:
    """
    event_type: agent_run | insight_generated | decision_applied | copilot_query | user_action
    """
    pl = {"ts": datetime.now(timezone.utc).isoformat(), **payload}
    _bq_audit(event_type, organization_id, entity_id, user_id, pl)
    if os.environ.get("AUDIT_STDOUT"):
        print(json.dumps({"audit": event_type, "org": organization_id, "payload": pl}, default=str))


def log_agent_run_audit(organization_id: str, agent_name: str, insights_generated: int, runtime_seconds: float, errors: Optional[list] = None) -> None:
    log_audit(
        "agent_run",
        organization_id,
        entity_id=agent_name,
        agent_name=agent_name,
        insights_generated=insights_generated,
        runtime_seconds=runtime_seconds,
        errors=errors or [],
    )


def log_insight_generated(organization_id: str, insight_id: str, client_id: Optional[int] = None) -> None:
    log_audit("insight_generated", organization_id, entity_id=insight_id, insight_id=insight_id, client_id=client_id)


def log_decision_applied(organization_id: str, insight_id: str, user_id: Optional[str], history_id: Optional[str] = None) -> None:
    log_audit("decision_applied", organization_id, entity_id=insight_id, user_id=user_id, insight_id=insight_id, history_id=history_id)


def log_copilot_query(organization_id: str, insight_id: str, user_id: Optional[str] = None) -> None:
    log_audit("copilot_query", organization_id, entity_id=insight_id, user_id=user_id, insight_id=insight_id)


def log_user_action(organization_id: str, action: str, user_id: Optional[str] = None, entity_id: Optional[str] = None, **extra: Any) -> None:
    log_audit("user_action", organization_id, entity_id=entity_id, user_id=user_id, action=action, **extra)
