"""
Copilot tools: discover_tables (synonym-aware ranking) + run_bigquery_sql. Read-only. All datasets from org config (no hardcoded names).
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, List, Optional, Set

from .concept_map import expand_intent_tokens
from .defaults import get_discover_tables_limit, get_max_tables_per_dataset
from .schema_cache import schema_cache_get, schema_cache_set

COPILOT_TOOLS = [
    {
        "name": "discover_tables",
        "description": "Get candidate tables for a question from your configured datasets. Returns project, dataset, table, columns. Use before writing SQL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "Short intent from the user question."},
                "limit": {"type": "integer", "description": "Max candidates (default 20)."},
            },
            "required": ["intent"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_bigquery_sql",
        "description": "Execute read-only SELECT. Returns rows, schema, row_count. No DML/DDL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Single SELECT query."},
                "dry_run": {"type": "boolean", "description": "Validate only (default false)."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]


def _normalize_tool_arguments(arguments: Any) -> dict:
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
    out = []
    for r in rows:
        row = {}
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
            elif v is not None and isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                row[k] = None
            else:
                row[k] = v
        out.append(row)
    return out


def _rank_tables_by_intent(tables: List[dict], intent: str, organization_id: Optional[str] = None) -> List[dict]:
    """Rank by keyword + synonym overlap (score only). No hardcoded dataset types; all tables from org config."""
    tokens = expand_intent_tokens(intent)
    scored: List[tuple[float, dict]] = []
    for t in tables:
        table_name = (t.get("table_name") or "").lower()
        cols = t.get("columns") or []
        col_names = [(c.get("name") or "").lower() for c in cols if c.get("name")]
        all_text = table_name + " " + " ".join(col_names)
        all_tokens = set(re.findall(r"\w+", all_text))
        match = len(tokens & all_tokens)
        col_match = sum(1 for c in col_names if c in tokens)
        score = match + 0.5 * col_match
        scored.append((score, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored]


def _apply_per_dataset_cap(ranked: List[dict], limit: int, max_per_dataset: int) -> List[dict]:
    """Ensure no single dataset dominates: at most max_per_dataset tables per dataset, then take up to limit total."""
    per_ds_count: dict = {}
    out: List[dict] = []
    for t in ranked:
        if len(out) >= limit:
            break
        ds = (t.get("dataset") or "").strip()
        n = per_ds_count.get(ds, 0)
        if n < max_per_dataset:
            per_ds_count[ds] = n + 1
            out.append(t)
    return out


def discover_tables(
    intent: str,
    limit: int = 20,
    organization_id: Optional[str] = None,
    exclude_datasets: Optional[Set[str]] = None,
) -> List[dict]:
    """Ranked candidate tables from org-configured datasets only. Per-dataset cap for multi-dataset representation.
    When exclude_datasets is set, return only tables from other datasets (for retry/fallback); cache is skipped."""
    from ..clients.bigquery import list_tables_for_discovery

    limit = min(limit or get_discover_tables_limit(), 50)
    max_per_ds = get_max_tables_per_dataset()
    cache_key = f"{organization_id}:{intent}" if (organization_id or "").strip() else intent
    if not exclude_datasets:
        cached = schema_cache_get(cache_key)
        if cached is not None:
            return cached[:limit]
    raw = list_tables_for_discovery(organization_id=organization_id)
    if exclude_datasets:
        raw = [t for t in raw if (t.get("dataset") or "").strip() not in exclude_datasets]
    if not raw:
        return []
    ranked = _rank_tables_by_intent(raw, intent, organization_id=organization_id)
    capped = _apply_per_dataset_cap(ranked, limit, max_per_ds)
    result = []
    for t in capped:
        columns = []
        for c in (t.get("columns") or []):
            if not c.get("name"):
                continue
            columns.append({"name": c.get("name"), "data_type": c.get("data_type")})
        result.append({
            "project": t.get("project"),
            "dataset": t.get("dataset"),
            "table": t.get("table_name"),
            "columns": columns,
            "last_updated": t.get("last_updated"),
            "sample_row": {},
        })
    if not exclude_datasets:
        schema_cache_set(cache_key, result)
    return result


def run_bigquery_sql(
    sql: str,
    organization_id: str,
    client_id: int,
    dry_run: bool = False,
    max_rows: int = 500,
    timeout_sec: float = 45.0,
) -> dict:
    """Execute read-only BigQuery SQL. Returns rows, schema, row_count, stats, error. Default 45s for high-latency BQ."""
    from ..clients.bigquery import run_bigquery_sql_readonly

    out = run_bigquery_sql_readonly(
        sql=sql,
        client_id=client_id,
        organization_id=organization_id,
        max_rows=max_rows,
        timeout_sec=timeout_sec,
        dry_run=dry_run,
    )
    rows = out.get("rows") or []
    out["rows"] = _serialize_rows(rows)
    out["row_count"] = len(out["rows"])
    return out


def execute_tool(
    organization_id: str,
    client_id: int,
    tool_name: str,
    arguments: Optional[dict] = None,
) -> str:
    """Execute discover_tables or run_bigquery_sql."""
    args = _normalize_tool_arguments(arguments)
    cid = int(client_id) if client_id is not None else 1

    if tool_name == "discover_tables":
        intent = (args.get("intent") or "").strip() or "analytics"
        limit = args.get("limit")
        if limit is not None:
            try:
                limit = min(50, max(1, int(limit)))
            except (TypeError, ValueError):
                limit = get_discover_tables_limit()
        else:
            limit = get_discover_tables_limit()
        candidates = discover_tables(intent, limit=limit, organization_id=organization_id)
        return json.dumps({"candidates": candidates})

    if tool_name == "run_bigquery_sql":
        query = (args.get("query") or "").strip()
        if not query:
            return json.dumps({"rows": [], "schema": [], "row_count": 0, "stats": {}, "error": "Missing query."})
        dry_run = bool(args.get("dry_run", False))
        out = run_bigquery_sql(query, organization_id=organization_id, client_id=cid, dry_run=dry_run)
        return json.dumps(out)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
