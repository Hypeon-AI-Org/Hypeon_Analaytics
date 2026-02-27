"""
Copilot tools: single tool (run_sql) for on-demand data from hypeon_marts and hypeon_marts_ads only.
No staging, cache, or raw datasets.
"""
from __future__ import annotations

import json
import math
from typing import Any, Optional

# run_sql: ONLY hypeon_marts.fct_sessions and hypeon_marts_ads.fct_ad_spend. No fallback.
COPILOT_TOOLS = [
    {
        "name": "run_sql",
        "description": "Run a single SELECT (or WITH ... SELECT) against hypeon_marts or hypeon_marts_ads only. Allowed tables: hypeon_marts.fct_sessions (events, item_id, utm_source), hypeon_marts_ads.fct_ad_spend (channel, cost, clicks). Use backtick-quoted names: `project.hypeon_marts.fct_sessions`, `project.hypeon_marts_ads.fct_ad_spend`. Returns JSON with 'rows' and optional 'error'. Do NOT reference ads_daily_staging, ga4_daily_staging, or raw datasets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A single SELECT SQL query. Only tables from the injected schema (hypeon_marts, hypeon_marts_ads) are allowed.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]


def _normalize_tool_arguments(arguments: Any) -> dict:
    """Ensure tool arguments are always a dict (API may return a JSON string)."""
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def execute_tool(
    organization_id: str,
    client_id: int,
    tool_name: str,
    arguments: Optional[dict] = None,
) -> str:
    """
    Execute a Copilot tool. Only run_sql; it queries hypeon_marts and hypeon_marts_ads only. No fallback.
    """
    args = _normalize_tool_arguments(arguments)
    cid = int(client_id) if client_id is not None else 1

    if tool_name == "run_sql":
        from ..clients.bigquery import run_readonly_query
        query = (args.get("query") or "").strip()
        if not query:
            return json.dumps({"rows": [], "error": "Missing query."})
        out = run_readonly_query(
            sql=query,
            client_id=cid,
            organization_id=organization_id,
            max_rows=500,
            timeout_sec=15.0,
        )
        rows = out.get("rows") or []
        serialized = []
        for r in rows:
            row = {}
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
                elif v is not None and isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    row[k] = None
                else:
                    row[k] = v
            serialized.append(row)
        return json.dumps({"rows": serialized, "error": out.get("error"), "row_count": len(serialized)})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
