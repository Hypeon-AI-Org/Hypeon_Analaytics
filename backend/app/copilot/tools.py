"""
Copilot tools: single tool (run_sql) for on-demand data fetch from ADS_DATASET and GA4_DATASET only.
LLM calls run_sql when needed; executor runs BigQuery and returns JSON.
"""
from __future__ import annotations

import json
import math
from typing import Any, Optional

# Universal tool: run_sql. LLM generates the SQL from the user query and knowledge-base schema; only ADS_DATASET and GA4_DATASET.
COPILOT_TOOLS = [
    {
        "name": "run_sql",
        "description": "Universal tool to fetch any data from the allowed datasets. Generate a single SELECT (or WITH ... SELECT) query from the user's question and the schema in the knowledge base. Only tables in ADS_DATASET and GA4_DATASET are allowed; use backtick-quoted table names (e.g. `project.dataset.events_*`). Returns JSON with 'rows' and optional 'error'. Use for every data question: totals, breakdowns by date/device/campaign, item view counts (GA4: event_name IN ('view_item','view_item_list'), UNNEST(COALESCE(items,[])) with item_id), event counts, or any other analysis. Scope Ads by customer_id; limit GA4 scans with event_date filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A single SELECT (or WITH ... SELECT) SQL query. Use backtick-quoted table names: `project.dataset.table`. Scope by client_id/customer_id and date as needed.",
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
    Execute a Copilot tool and return JSON string result.
    Only run_sql is supported; it queries ADS_DATASET and GA4_DATASET only.
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
