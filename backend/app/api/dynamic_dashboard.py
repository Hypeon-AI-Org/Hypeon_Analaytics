"""
Dynamic Dashboard API: schema-agnostic discovery, preview, and aggregations.
Uses org-configured BigQuery datasets only. Does not modify Copilot state.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth import get_organization_id, require_any_auth
from ..clients.bigquery import list_tables_for_discovery, run_readonly_query

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dynamic-dashboard",
    tags=["dynamic-dashboard"],
    dependencies=[Depends(require_any_auth)],
)


def _org_id(request: Request) -> str:
    return get_organization_id(request) or ""


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
def _safe_serialize(obj: Any) -> Any:
    """Make values JSON-serializable (dates, etc.)."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_serialize(v) for v in obj]
    return str(obj)


# ---------------------------------------------------------------------------
# Datasets (list org-configured datasets)
# ---------------------------------------------------------------------------
@router.get("/datasets")
def get_datasets(request: Request):
    """List datasets configured for this organization (project, dataset, location). Read-only from Firestore."""
    try:
        from ..auth.firestore_user import get_org_all_dataset_configs
        org = _org_id(request)
        if not org:
            return JSONResponse(status_code=200, content={"datasets": [], "message": "Organization required."})
        configs = get_org_all_dataset_configs(org)
        datasets = [
            {
                "bq_project": c.get("bq_project"),
                "bq_dataset": c.get("bq_dataset"),
                "bq_location": c.get("bq_location") or "europe-north2",
            }
            for c in configs
        ]
        return JSONResponse(status_code=200, content={"datasets": datasets})
    except Exception as e:
        logger.exception("Dynamic dashboard datasets failed: %s", e)
        return JSONResponse(status_code=200, content={"datasets": []})


# ---------------------------------------------------------------------------
# Tables (list tables with schema for org)
# ---------------------------------------------------------------------------
@router.get("/tables")
def get_tables(request: Request):
    """List all tables (with columns) for this organization. Uses same discovery as Copilot; read-only."""
    try:
        org = _org_id(request)
        if not org:
            return JSONResponse(
                status_code=200,
                content={"tables": [], "message": "Organization required."},
            )
        tables = list_tables_for_discovery(organization_id=org)
        out = [
            {
                "project": t.get("project"),
                "dataset": t.get("dataset"),
                "table_name": t.get("table_name"),
                "columns": t.get("columns") or [],
            }
            for t in tables
        ]
        return JSONResponse(status_code=200, content={"tables": out})
    except Exception as e:
        logger.exception("Dynamic dashboard tables failed: %s", e)
        return JSONResponse(status_code=200, content={"tables": []})


# ---------------------------------------------------------------------------
# Table preview (SELECT * LIMIT N)
# ---------------------------------------------------------------------------
class PreviewBody(BaseModel):
    project: str = Field(..., min_length=1)
    dataset: str = Field(..., min_length=1)
    table: str = Field(..., min_length=1)
    limit: int = Field(100, ge=1, le=1000)


def _table_key(project: str, dataset: str, table: str) -> tuple[str, str, str]:
    return (str(project).strip().lower(), str(dataset).strip().lower(), str(table).strip().lower())


def _allowed_tables_set(organization_id: str) -> set[tuple[str, str, str]]:
    from ..copilot.schema_cache_firestore import get_allowed_tables_set
    return get_allowed_tables_set(organization_id, list_tables_fn=list_tables_for_discovery)


@router.post("/preview")
def post_preview(request: Request, body: PreviewBody):
    """Run SELECT * FROM `project.dataset.table` LIMIT N. Table must be in org's allowed set."""
    org = _org_id(request)
    if not org:
        return JSONResponse(status_code=400, content={"error": "Organization required."})
    allowed = _allowed_tables_set(org)
    key = _table_key(body.project, body.dataset, body.table)
    if key not in allowed:
        return JSONResponse(
            status_code=400,
            content={"error": f"Table {body.dataset}.{body.table} is not available for your organization."},
        )
    safe_table = f"`{body.project}.{body.dataset}.{body.table}`"
    sql = f"SELECT * FROM {safe_table} LIMIT {body.limit}"
    result = run_readonly_query(sql, client_id=1, organization_id=org, max_rows=body.limit)
    if result.get("error"):
        return JSONResponse(status_code=400, content={"error": result["error"]})
    rows = _safe_serialize(result.get("rows") or [])
    return JSONResponse(status_code=200, content={"rows": rows})


# ---------------------------------------------------------------------------
# Aggregate (GROUP BY one column, aggregate one numeric column)
# ---------------------------------------------------------------------------
class AggregateBody(BaseModel):
    project: str = Field(..., min_length=1)
    dataset: str = Field(..., min_length=1)
    table: str = Field(..., min_length=1)
    group_by_column: str = Field(..., min_length=1)
    metric_column: str = Field(..., min_length=1)
    agg: str = Field("sum", pattern="^(sum|avg|count|min|max)$")
    limit: int = Field(100, ge=1, le=500)


# Safe identifier (column names from discovery are safe; we validate they exist in table schema)
_COLUMN_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_column_name(name: str) -> bool:
    return bool(name and _COLUMN_PATTERN.match(name.strip()))


@router.post("/aggregate")
def post_aggregate(request: Request, body: AggregateBody):
    """Run SELECT group_by_column, AGG(metric_column) FROM table GROUP BY group_by_column. Columns must exist in table schema."""
    org = _org_id(request)
    if not org:
        return JSONResponse(status_code=400, content={"error": "Organization required."})
    if not _validate_column_name(body.group_by_column) or not _validate_column_name(body.metric_column):
        return JSONResponse(status_code=400, content={"error": "Invalid column name."})
    allowed = _allowed_tables_set(org)
    key = _table_key(body.project, body.dataset, body.table)
    if key not in allowed:
        return JSONResponse(
            status_code=400,
            content={"error": f"Table {body.dataset}.{body.table} is not available for your organization."},
        )
    tables = list_tables_for_discovery(organization_id=org)
    columns = None
    for t in tables:
        if _table_key(t.get("project"), t.get("dataset"), t.get("table_name")) == key:
            columns = {c.get("name") for c in (t.get("columns") or []) if c.get("name")}
            break
    if not columns:
        return JSONResponse(status_code=400, content={"error": "Table not found in schema."})
    gb, mc = body.group_by_column.strip(), body.metric_column.strip()
    if gb not in columns or mc not in columns:
        return JSONResponse(status_code=400, content={"error": "group_by_column or metric_column not in table schema."})
    agg_upper = body.agg.upper()
    safe_table = f"`{body.project}.{body.dataset}.{body.table}`"
    sql = f"SELECT `{gb}` AS group_value, {agg_upper}(`{mc}`) AS metric_value FROM {safe_table} GROUP BY `{gb}` ORDER BY metric_value DESC LIMIT {body.limit}"
    result = run_readonly_query(sql, client_id=1, organization_id=org, max_rows=body.limit)
    if result.get("error"):
        return JSONResponse(status_code=400, content={"error": result["error"]})
    rows = _safe_serialize(result.get("rows") or [])
    return JSONResponse(status_code=200, content={"rows": rows})


# ---------------------------------------------------------------------------
# Time series (date column + numeric column, optional truncation)
# ---------------------------------------------------------------------------
class TimeSeriesBody(BaseModel):
    project: str = Field(..., min_length=1)
    dataset: str = Field(..., min_length=1)
    table: str = Field(..., min_length=1)
    date_column: str = Field(..., min_length=1)
    metric_column: str = Field(..., min_length=1)
    agg: str = Field("sum", pattern="^(sum|avg|count|min|max)$")
    date_trunc: str = Field("day", pattern="^(day|week|month)$")
    limit: int = Field(366, ge=1, le=1000)


@router.post("/time-series")
def post_time_series(request: Request, body: TimeSeriesBody):
    """Run SELECT date_trunc(date_column), AGG(metric_column) FROM table GROUP BY 1 ORDER BY 1. For line charts over time."""
    org = _org_id(request)
    if not org:
        return JSONResponse(status_code=400, content={"error": "Organization required."})
    if not _validate_column_name(body.date_column) or not _validate_column_name(body.metric_column):
        return JSONResponse(status_code=400, content={"error": "Invalid column name."})
    allowed = _allowed_tables_set(org)
    key = _table_key(body.project, body.dataset, body.table)
    if key not in allowed:
        return JSONResponse(
            status_code=400,
            content={"error": f"Table {body.dataset}.{body.table} is not available for your organization."},
        )
    tables = list_tables_for_discovery(organization_id=org)
    columns = None
    for t in tables:
        if _table_key(t.get("project"), t.get("dataset"), t.get("table_name")) == key:
            columns = {c.get("name") for c in (t.get("columns") or []) if c.get("name")}
            break
    if not columns:
        return JSONResponse(status_code=400, content={"error": "Table not found in schema."})
    dc, mc = body.date_column.strip(), body.metric_column.strip()
    if dc not in columns or mc not in columns:
        return JSONResponse(status_code=400, content={"error": "date_column or metric_column not in table schema."})
    trunc = body.date_trunc.strip().lower()
    # BigQuery: DATE_TRUNC expects TIMESTAMP; cast DATE to TIMESTAMP for consistency
    trunc_sql = f"DATE_TRUNC(CAST(`{dc}` AS TIMESTAMP), {trunc.upper()})"
    agg_upper = body.agg.upper()
    safe_table = f"`{body.project}.{body.dataset}.{body.table}`"
    sql = f"SELECT {trunc_sql} AS date_value, {agg_upper}(`{mc}`) AS metric_value FROM {safe_table} GROUP BY 1 ORDER BY 1 LIMIT {body.limit}"
    result = run_readonly_query(sql, client_id=1, organization_id=org, max_rows=body.limit)
    if result.get("error"):
        return JSONResponse(status_code=400, content={"error": result["error"]})
    rows = _safe_serialize(result.get("rows") or [])
    return JSONResponse(status_code=200, content={"rows": rows})
