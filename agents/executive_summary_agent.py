#!/usr/bin/env python3
"""
Executive Intelligence Agent: runs daily, produces one Business Health Summary per org/client.
Output: top_risks, top_opportunities, overall_growth_state, recommended_focus_today.
Stored in executive_summaries.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.clients.bigquery import (
    list_insights,
    get_decision_history,
    insert_executive_summary,
)
from backend.app.config_loader import get
from backend.app.insight_ranker import top_per_client
from backend.app.observability.logger import log_agent_run


def get_organization_id() -> str:
    return os.environ.get("ORGANIZATION_ID", "default")


def get_run_date() -> date:
    raw = os.environ.get("RUN_DATE")
    if raw:
        return date.fromisoformat(raw)
    return (datetime.utcnow() - timedelta(days=1)).date()


def run_executive_summary_agent(
    organization_id: str,
    as_of_date: date,
    client_ids: list[int] | None = None,
    write: bool = True,
) -> list[dict]:
    """
    Build Business Health Summary from top insights and recent decisions.
    Returns list of summary records (one per client if client_ids set, else one for org).
    """
    if client_ids is None:
        client_ids = [int(x) for x in os.environ.get("CLIENT_IDS", "1").split(",") if x.strip()]

    summaries = []
    top_n = get("top_insights_per_client", 5)

    for client_id in client_ids:
        insights = list_insights(organization_id, client_id=client_id, status=None, limit=200, offset=0)
        ranked = top_per_client(insights, top_n=top_n)
        risks = []
        opportunities = []
        for i in ranked:
            sev = (i.get("severity") or "").lower()
            it = (i.get("insight_type") or "").lower()
            summary = (i.get("summary") or "")[:200]
            if sev in ("high", "critical") or "waste" in it or "decline" in it:
                risks.append(summary or it)
            elif "opportunity" in it or "scale" in it:
                opportunities.append(summary or it)

        decisions = get_decision_history(organization_id, client_id=client_id, status="applied", limit=10)
        applied_count = len(decisions)

        if not risks:
            risks = ["No high-severity risks identified."]
        if not opportunities:
            opportunities = ["No scaling opportunities flagged."]

        if applied_count > 0 and len(ranked) > 0:
            growth_state = "Active optimization in progress."
        elif len(ranked) > 0:
            growth_state = "Insights available; review recommended."
        else:
            growth_state = "Stable; no urgent actions."

        focus = "Budget redistribution."
        if risks and not opportunities:
            focus = "Address top risks first (e.g. pause waste, fix ROAS decline)."
        elif opportunities and not risks:
            focus = "Scale top performers; increase budget on high ROAS."
        elif risks and opportunities:
            focus = "Balance risk mitigation and scaling opportunities."

        rec = {
            "organization_id": organization_id,
            "client_id": client_id,
            "summary_date": as_of_date,
            "top_risks": " | ".join(risks[:5]),
            "top_opportunities": " | ".join(opportunities[:5]),
            "overall_growth_state": growth_state,
            "recommended_focus_today": focus,
        }
        summaries.append(rec)
        if write:
            insert_executive_summary(
                organization_id=organization_id,
                summary_date=as_of_date,
                top_risks=rec["top_risks"],
                top_opportunities=rec["top_opportunities"],
                overall_growth_state=rec["overall_growth_state"],
                recommended_focus_today=rec["recommended_focus_today"],
                client_id=client_id,
            )
    return summaries


def main() -> int:
    org = get_organization_id()
    as_of = get_run_date()
    run_executive_summary_agent(org, as_of, write=True)
    log_agent_run(
        organization_id=org,
        agent_name="executive_summary_agent",
        insights_generated=0,
        runtime_seconds=0,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
