#!/usr/bin/env python3
"""
Entrypoint for agents: load client list, run rules_engine.generate_insights per client/date.
Invoked by Cloud Composer DAG or Cloud Scheduler + Cloud Run job.
Env: BQ_PROJECT, ANALYTICS_DATASET, CLIENT_IDS (comma-separated), RUN_DATE (YYYY-MM-DD).
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.rules_engine import generate_insights


def get_client_ids() -> list[int]:
    """Client list from env or default single client."""
    raw = os.environ.get("CLIENT_IDS", "1")
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def get_run_date() -> date:
    """Run date from env or yesterday."""
    raw = os.environ.get("RUN_DATE")
    if raw:
        return date.fromisoformat(raw)
    return (datetime.utcnow() - timedelta(days=1)).date()


def main() -> int:
    client_ids = get_client_ids()
    as_of = get_run_date()
    print(f"Running agents for clients {client_ids} as_of {as_of}")
    total = 0
    for cid in client_ids:
        try:
            insights = generate_insights(cid, as_of, write=True)
            total += len(insights)
            print(f"  client_id={cid}: {len(insights)} insights")
        except Exception as e:
            print(f"  client_id={cid}: error {e}", file=sys.stderr)
            raise
    print(f"Total insights: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
