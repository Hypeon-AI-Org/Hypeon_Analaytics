"""
Schema summary: LLM-generated short description of an org's BigQuery datasets/tables/columns.
Computed on refresh (e.g. after login); stored in Firestore with the schema cache.
Copilot uses this to answer questions faster without re-discovering schema every time.
"""
from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Max length for the summary stored and passed to the LLM (avoid token overflow).
MAX_SUMMARY_CHARS = 8000


def _tables_to_compact_repr(tables: List[dict]) -> str:
    """Build a compact, LLM-friendly list of dataset.table and columns (no row data)."""
    lines = []
    for t in (tables or [])[:100]:
        if not isinstance(t, dict):
            continue
        project = (t.get("project") or t.get("table_catalog") or "").strip()
        dataset = (t.get("dataset") or t.get("table_schema") or "").strip()
        table_name = (t.get("table_name") or "").strip()
        if not table_name:
            continue
        full = f"{project}.{dataset}.{table_name}" if project else f"{dataset}.{table_name}"
        cols = t.get("columns") or []
        col_names = []
        for c in cols[:50]:
            if isinstance(c, dict) and c.get("name"):
                col_names.append(str(c.get("name")))
            elif isinstance(c, dict) and c.get("data_type"):
                col_names.append(f"{c.get('name', '')}({c.get('data_type')})")
        lines.append(f"- {full}: {', '.join(col_names) if col_names else '(no columns)'}")
    return "\n".join(lines) if lines else "(no tables)"


def summarize_schema_with_llm(
    organization_id: str,
    tables: List[dict],
) -> Optional[str]:
    """
    Use the configured LLM to produce a short, semantic summary of the org's datasets and tables.
    Returns a string suitable for Copilot context (what data exists, what it's for). None on failure.
    """
    if not tables:
        return None
    compact = _tables_to_compact_repr(tables)
    if not compact or compact == "(no tables)":
        return None
    prompt = f"""You are a data catalog assistant. Below is a list of BigQuery tables and their columns for one organization. The data can be from Google Ads, GA4, Meta Ads, Pinterest, or other marketing/analytics sources.

Tables and columns (project.dataset.table: col1, col2, ...):
{compact[:12000]}

Write a short, structured summary (plain text, no markdown) that:
1. Lists which data sources or datasets exist (e.g. "Google Ads campaign metrics", "GA4 events", "Meta Ads").
2. For each logical group, mention the main tables and what they contain (e.g. spend, revenue, ROAS, sessions, conversions).
3. Note important columns for analytics (dates, IDs, dimensions, metrics).

Keep the summary under 500 words so it can be used as context for a Copilot that answers questions about this data. Do not invent tables or columns; only describe what is listed above."""

    try:
        from ..copilot_synthesizer import get_llm_client
        llm = get_llm_client()
        raw = llm(prompt)
        if isinstance(raw, dict):
            raw = raw.get("summary") or raw.get("explanation") or raw.get("tldr") or json.dumps(raw)
        if not isinstance(raw, str) or not raw.strip():
            return None
        summary = raw.strip()[:MAX_SUMMARY_CHARS]
        logger.info("Schema summary generated | org_id=%s length=%d", organization_id, len(summary))
        return summary
    except Exception as e:
        logger.warning("Schema summary LLM failed: %s", e, exc_info=True)
        return None
