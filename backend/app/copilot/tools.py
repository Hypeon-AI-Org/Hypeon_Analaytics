"""
Copilot tools: run_sql (marts) and run_sql_raw (raw GA4/Ads fallback).
"""
from __future__ import annotations

import json
import math
from typing import Any, Optional

COPILOT_TOOLS = [
    {
        "name": "run_sql",
        "description": "Run a single SELECT (or WITH ... SELECT) against hypeon_marts or hypeon_marts_ads only. Allowed tables: hypeon_marts.fct_sessions (events, item_id, utm_source), hypeon_marts_ads.fct_ad_spend (channel, cost, clicks). Use backtick-quoted names: `project.hypeon_marts.fct_sessions`, `project.hypeon_marts_ads.fct_ad_spend`. Returns JSON with 'rows' and optional 'error'. Prefer this over run_sql_raw when marts have the data.",
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
    {
        "name": "run_sql_raw",
        "description": "Run a read-only SELECT against raw GA4 or Ads tables when marts (run_sql) don't have the needed data or returned empty. Allowed: GA4 events_* tables, Ads ads_AccountBasicStats_* tables. Use backtick-quoted names. Always include LIMIT and, for GA4, filter by event_date. Returns same JSON shape as run_sql (rows, error). Use only when run_sql is insufficient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A single SELECT SQL query. Only GA4 events_* and Ads ads_AccountBasicStats_* tables are allowed. Include LIMIT and date filter for GA4.",
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


def _serialize_rows(rows: list[dict]) -> list[dict]:
    """Serialize BigQuery row dicts for JSON (dates, NaN)."""
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
    return serialized


def execute_tool(
    organization_id: str,
    client_id: int,
    tool_name: str,
    arguments: Optional[dict] = None,
) -> str:
    """
    Execute a Copilot tool: run_sql (marts) or run_sql_raw (raw GA4/Ads fallback).
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
        serialized = _serialize_rows(rows)
        return json.dumps({"rows": serialized, "error": out.get("error"), "row_count": len(serialized)})

    if tool_name == "run_sql_raw":
        from ..clients.bigquery import run_readonly_query_raw
        query = (args.get("query") or "").strip()
        if not query:
            return json.dumps({"rows": [], "error": "Missing query."})
        out = run_readonly_query_raw(
            sql=query,
            client_id=cid,
            organization_id=organization_id,
            max_rows=500,
            timeout_sec=20.0,
        )
        rows = out.get("rows") or []
        serialized = _serialize_rows(rows)
        return json.dumps({"rows": serialized, "error": out.get("error"), "row_count": len(serialized)})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
