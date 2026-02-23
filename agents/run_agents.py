#!/usr/bin/env python3
"""
Entrypoint for agents: load client list, run rules_engine.generate_insights per client/date.
Enterprise: organization_id, workspace_id; incremental since_date; observability logging.
Env: BQ_PROJECT, ANALYTICS_DATASET, CLIENT_IDS, RUN_DATE, ORGANIZATION_ID, WORKSPACE_ID, INCREMENTAL_DAYS.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.rules_engine import generate_insights
from backend.app.observability.logger import log_agent_run
from backend.app.config_loader import get
from backend.app.clients.bigquery import insert_system_health, get_recent_insight_hashes
from backend.app.insight_suppressor import suppress_noise
from backend.app.audit_logger import log_agent_run_audit


def get_organization_id() -> str:
    return os.environ.get("ORGANIZATION_ID", "default")


def get_workspace_id():
    return os.environ.get("WORKSPACE_ID")


def get_client_ids() -> list[int]:
    raw = os.environ.get("CLIENT_IDS", "1")
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def get_run_date() -> date:
    raw = os.environ.get("RUN_DATE")
    if raw:
        return date.fromisoformat(raw)
    return (datetime.utcnow() - timedelta(days=1)).date()


def get_since_date(as_of: date) -> date | None:
    """For incremental: only process data since last run (config agent_incremental_days)."""
    days = os.environ.get("INCREMENTAL_DAYS") or get("agent_incremental_days")
    if days is None or int(days) <= 0:
        return None
    return as_of - timedelta(days=int(days))


def main() -> int:
    organization_id = get_organization_id()
    workspace_id = get_workspace_id()
    client_ids = get_client_ids()
    as_of = get_run_date()
    since = get_since_date(as_of)
    print(f"Running agents org={organization_id} clients={client_ids} as_of={as_of} since={since}")
    total = 0
    start = time.perf_counter()
    errors: list[str] = []
    cooldown_days = get("insight_cooldown_days", 5)
    def existing_hashes(org: str, cid: str):
        return get_recent_insight_hashes(org, cid, since_days=cooldown_days or 7)
    for cid in client_ids:
        try:
            insights = generate_insights(
                cid,
                as_of,
                organization_id=organization_id,
                workspace_id=workspace_id,
                write=False,
                merge=True,
                rank=True,
                since_date=since,
            )
            if insights:
                insights = suppress_noise(insights, existing_insight_hashes=existing_hashes)
            if insights:
                from backend.app.clients.bigquery import insert_insights
                insert_insights(insights)
            total += len(insights)
            print(f"  client_id={cid}: {len(insights)} insights")
        except Exception as e:
            errors.append(f"client_id={cid}: {e}")
            print(f"  client_id={cid}: error {e}", file=sys.stderr)
            raise
    elapsed = time.perf_counter() - start
    log_agent_run(
        organization_id=organization_id,
        agent_name="run_agents",
        insights_generated=total,
        runtime_seconds=elapsed,
        errors=errors if errors else None,
    )
    log_agent_run_audit(organization_id, "run_agents", total, elapsed, errors if errors else None)
    try:
        insert_system_health(
            organization_id=organization_id,
            agent_name="run_agents",
            agent_runtime_seconds=elapsed,
            failures=len(errors),
            insight_volume=total,
            processing_latency_seconds=elapsed,
            status="ok" if not errors else "partial",
            details="; ".join(errors) if errors else None,
        )
    except Exception:
        pass
    print(f"Total insights: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
