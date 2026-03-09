"""
Copilot schema cache in Firestore: per-org cache of dataset/table/column list for faster Copilot.
Document: copilot_schema_cache/{organization_id}. Fields: updated_at (epoch sec), bq_project, tables.
Cache is valid for 24 hours; after that Copilot uses live discovery until refresh is called.
"""
from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

COLLECTION = "copilot_schema_cache"
TTL_SECONDS = 24 * 3600  # 24 hours


def _get_firestore():
    try:
        from ..auth.firestore_user import _get_firestore as _fs
        return _fs()
    except Exception:
        return None


def get_cached_schema(organization_id: str) -> Optional[dict[str, Any]]:
    """
    Return cached schema for org if present and updated_at within 24h.
    Returns { "updated_at": float, "bq_project": str, "tables": [ { project, dataset, table_name, columns } ] } or None.
    """
    if not (organization_id or "").strip():
        return None
    db = _get_firestore()
    if not db:
        return None
    try:
        doc = db.collection(COLLECTION).document(organization_id.strip()).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        updated_at = data.get("updated_at")
        if updated_at is None or (time.time() - float(updated_at)) > TTL_SECONDS:
            return None
        tables = data.get("tables")
        if not isinstance(tables, list):
            return None
        return {
            "updated_at": float(updated_at),
            "bq_project": data.get("bq_project") or "",
            "tables": tables,
        }
    except Exception as e:
        logger.debug("get_cached_schema failed: %s", e)
        return None


def set_cached_schema(
    organization_id: str,
    bq_project: str,
    tables: List[dict[str, Any]],
) -> bool:
    """
    Write schema cache for org. tables: list of { project, dataset, table_name, columns }.
    Returns True if written.
    """
    if not (organization_id or "").strip():
        return False
    db = _get_firestore()
    if not db:
        return False
    try:
        # Keep only JSON-serializable fields
        safe_tables = []
        for t in tables[:200]:
            if not isinstance(t, dict):
                continue
            safe_tables.append({
                "project": str(t.get("project") or t.get("table_catalog") or ""),
                "dataset": str(t.get("dataset") or t.get("table_schema") or ""),
                "table_name": str(t.get("table_name") or ""),
                "columns": [
                    {"name": str(c.get("name") or ""), "data_type": str(c.get("data_type") or "")}
                    for c in (t.get("columns") or []) if isinstance(c, dict)
                ][:100],
            })
        doc_ref = db.collection(COLLECTION).document(organization_id.strip())
        doc_ref.set({
            "updated_at": time.time(),
            "bq_project": (bq_project or "").strip(),
            "tables": safe_tables,
        })
        logger.info("Copilot schema cache written | org_id=%s tables=%d", organization_id, len(safe_tables))
        return True
    except Exception as e:
        logger.warning("set_cached_schema failed: %s", e)
        return False


def get_allowed_tables_set(organization_id: str, list_tables_fn=None):
    """
    Return set of (project, dataset, table_name) lowercase for this org.
    Uses cache first; if missing/expired, calls list_tables_fn(organization_id=organization_id)
    to build the set. list_tables_fn defaults to list_tables_for_discovery from clients.bigquery
    (injected to avoid circular import).
    """
    if not (organization_id or "").strip():
        return set()

    def _norm(t: dict) -> tuple:
        p = (t.get("project") or t.get("table_catalog") or "").strip().lower()
        d = (t.get("dataset") or t.get("table_schema") or "").strip().lower()
        tn = (t.get("table_name") or "").strip().lower()
        return (p, d, tn) if (p and d and tn) else None

    cached = get_cached_schema(organization_id)
    if cached and cached.get("tables"):
        out = set()
        for t in cached["tables"]:
            n = _norm(t)
            if n:
                out.add(n)
        return out

    if list_tables_fn is None:
        try:
            from ..clients.bigquery import list_tables_for_discovery
            list_tables_fn = list_tables_for_discovery
        except Exception:
            return set()
    tables = list_tables_fn(organization_id=organization_id) if list_tables_fn else []
    out = set()
    for t in (tables or []):
        n = _norm(t)
        if n:
            out.add(n)
    return out
