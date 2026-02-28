"""
Knowledge base for Copilot: schema ONLY from hypeon_marts and hypeon_marts_ads INFORMATION_SCHEMA.
No static table names. No fallback to discovery or raw datasets. If schema fetch fails, return error.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# In-process cache for get_schema_for_copilot() to avoid re-reading on every request.
_SCHEMA_CACHE: str | None = None


def get_bq_project() -> str:
    return os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")


def get_bq_source_project() -> str:
    """Project where GA4 raw events live (BQ_SOURCE_PROJECT or BQ_PROJECT)."""
    return os.environ.get("BQ_SOURCE_PROJECT") or get_bq_project()


def get_analytics_dataset() -> str:
    return os.environ.get("ANALYTICS_DATASET", "analytics")


def get_ads_dataset() -> str:
    """Dataset for Ads (from .env ADS_DATASET, e.g. 146568). Never delete."""
    return os.environ.get("ADS_DATASET", "146568")


def get_ga4_dataset() -> str:
    """Dataset for GA4 (from .env GA4_DATASET, e.g. analytics_444259275). Never delete."""
    return os.environ.get("GA4_DATASET", "analytics_444259275")


def get_marts_dataset() -> str:
    """Marts dataset (hypeon_marts). Primary schema source for Copilot."""
    return os.environ.get("MARTS_DATASET", "hypeon_marts")


def _discovery_path() -> Path:
    """Path to bigquery_discovery.json (repo root / bigquery_schema / bigquery_discovery.json)."""
    env_path = os.environ.get("BQ_DISCOVERY_PATH", "").strip()
    if env_path:
        return Path(env_path)
    # backend/app/copilot/knowledge_base.py -> parents[3] = repo root
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "bigquery_schema" / "bigquery_discovery.json"


def _samples_path() -> Path:
    """Path to copilot_samples.json (written by scripts/copilot_fetch_samples.py)."""
    env_path = os.environ.get("BQ_COPILOT_SAMPLES_PATH", "").strip()
    if env_path:
        return Path(env_path)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "bigquery_schema" / "copilot_samples.json"


def _raw_schema_path() -> Path:
    """Path to raw_copilot_schema.json (written by scripts/copilot_fetch_raw_schema.py)."""
    env_path = os.environ.get("BQ_RAW_COPILOT_SCHEMA_PATH", "").strip()
    if env_path:
        return Path(env_path)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "bigquery_schema" / "raw_copilot_schema.json"


def _marts_catalog_path() -> Path:
    """Path to copilot_marts_catalog.json (written by scripts/copilot_fetch_marts_catalog.py)."""
    env_path = os.environ.get("BQ_MARTS_CATALOG_PATH", "").strip()
    if env_path:
        return Path(env_path)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "bigquery_schema" / "copilot_marts_catalog.json"


# Max chars for raw schema section to avoid blowing the prompt.
_RAW_SCHEMA_MAX_CHARS = 15_000
_MARTS_CATALOG_MAX_CHARS = 12_000


def _load_samples_section() -> str:
    """Load optional sample rows and return a short 'Sample rows (for reference)' section, or empty string."""
    path = _samples_path()
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    if not isinstance(data, dict):
        return ""
    parts = ["", "## Sample rows (for reference)", ""]
    for ds_id, tables in sorted(data.items()):
        if not isinstance(tables, dict):
            continue
        for table_id, rows in sorted(tables.items()):
            if not isinstance(rows, list) or not rows:
                continue
            parts.append(f"### {ds_id}.{table_id}")
            for i, row in enumerate(rows[:2]):
                if isinstance(row, dict):
                    parts.append(json.dumps(row, default=str)[:800])
            parts.append("")
    if len(parts) <= 3:
        return ""
    return "\n".join(parts)


def _flatten_schema(schema: list[dict], prefix: str = "") -> list[tuple[str, str]]:
    """Flatten schema to (name, type) including nested RECORD/STRUCT fields for LLM readability."""
    out: list[tuple[str, str]] = []
    for col in schema or []:
        name = prefix + (col.get("name") or "?")
        typ = col.get("type") or "?"
        out.append((name, typ))
        if col.get("fields"):
            for sub in _flatten_schema(col["fields"], prefix=name + "."):
                out.append(sub)
    return out


# Max chars for schema section to avoid blowing the prompt (leave room for system text + tools).
_SCHEMA_MAX_CHARS = 55_000


def _format_live_marts_schema(rows: list[dict], project: str, marts: str) -> str:
    """Format live INFORMATION_SCHEMA rows into schema text (hypeon_marts + hypeon_marts_ads)."""
    from collections import defaultdict
    by_key = defaultdict(list)  # key = (dataset, table_name)
    for r in rows:
        ds = (r.get("dataset") or marts).strip()
        tn = (r.get("table_name") or "").strip()
        cn = (r.get("column_name") or "").strip()
        if tn and cn:
            by_key[(ds, tn)].append(cn)
    parts = [
        "## Database: BigQuery (read-only). Schema: hypeon_marts (GA4) + hypeon_marts_ads (Ads), live.",
        f"- Project: {project}. Datasets: hypeon_marts (europe-north2), hypeon_marts_ads (EU).",
        "- Use backtick-quoted names: `project.dataset.table`. Sessions: hypeon_marts; ad spend: hypeon_marts_ads.",
        "",
        "## Tables and columns (INFORMATION_SCHEMA)",
        "",
    ]
    for (ds, table_name) in sorted(by_key.keys()):
        cols = by_key[(ds, table_name)][:80]
        col_lines = [f"  - {c}" for c in cols]
        if len(by_key[(ds, table_name)]) > 80:
            col_lines.append(f"  - ... and {len(by_key[(ds, table_name)]) - 80} more")
        parts.append(f"- **{ds}.{table_name}**")
        parts.extend(col_lines)
        parts.append("")
    return "\n".join(parts)


def get_schema_for_copilot(use_cache: bool = True) -> str:
    """
    Schema ONLY from hypeon_marts and hypeon_marts_ads INFORMATION_SCHEMA (dynamic).
    No fallback. If fetch fails, return explicit error so the assistant tells the user.
    """
    global _SCHEMA_CACHE
    if use_cache and _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    project = get_bq_project()
    marts_ds = get_marts_dataset().strip()
    marts_ads_ds = os.environ.get("MARTS_ADS_DATASET", "hypeon_marts_ads").strip()

    try:
        from ..clients.bigquery import get_marts_schema_live
        live_rows = get_marts_schema_live()
        if not live_rows:
            err = _schema_error_message("Marts schema returned no tables. Ensure hypeon_marts and hypeon_marts_ads exist and have fct_sessions, fct_ad_spend.")
            _SCHEMA_CACHE = err
            return err
        schema_text = _format_live_marts_schema(live_rows, project, marts_ds)
        schema_text += _marts_only_rules(project, marts_ds, marts_ads_ds)
        catalog_section = get_marts_catalog_for_copilot()
        if catalog_section:
            schema_text += "\n" + catalog_section
        _SCHEMA_CACHE = schema_text
        return schema_text
    except Exception as e:
        err = _schema_error_message(f"Could not load marts schema: {str(e)[:200]}. Copilot uses only hypeon_marts and hypeon_marts_ads.")
        _SCHEMA_CACHE = err
        return err


def _schema_error_message(detail: str) -> str:
    """When schema fetch fails, return instructions so the assistant responds with a clear error."""
    return f"""## Database schema unavailable
- {detail}
- Do NOT use ads_daily_staging, ga4_daily_staging, analytics_cache, decision_store, or raw datasets.
- Tell the user: "The analytics schema could not be loaded. Please try again later or contact support."
"""


def get_marts_catalog_for_copilot() -> str:
    """
    Load copilot_marts_catalog.json (datasets, tables, schema, sample rows) and return
    a formatted string for the system prompt so the copilot knows what data exists.
    """
    path = _marts_catalog_path()
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    if not isinstance(data, dict):
        return ""
    project = data.get("project") or get_bq_project()
    hints = (data.get("hints") or "").strip()
    datasets = data.get("datasets") or {}
    parts = [
        "",
        "## Data catalog (schema + sample rows for accurate queries)",
        "Use this to see column types and example values. Prefer run_sql against these tables.",
        "",
    ]
    if hints:
        parts.append(f"Catalog hints: {hints}")
        parts.append("")
    for ds_id, ds_obj in sorted(datasets.items()):
        if not isinstance(ds_obj, dict):
            continue
        tables = ds_obj.get("tables") or {}
        for table_id, tbl in sorted(tables.items()):
            if not isinstance(tbl, dict):
                continue
            if tbl.get("error"):
                continue
            schema = tbl.get("schema") or []
            flat = _flatten_schema(schema)
            col_list = ", ".join(f"{n} ({t})" for n, t in flat[:50])
            if len(flat) > 50:
                col_list += f", ... +{len(flat) - 50} more"
            parts.append(f"- **{ds_id}.{table_id}** (project: {project})")
            parts.append(f"  Columns: {col_list}")
            for i, row in enumerate((tbl.get("sample_rows") or [])[:2]):
                if isinstance(row, dict):
                    parts.append(f"  Sample {i + 1}: {json.dumps(row, default=str)[:500]}")
            parts.append("")
    result = "\n".join(parts).strip()
    if len(result) > _MARTS_CATALOG_MAX_CHARS:
        result = result[:_MARTS_CATALOG_MAX_CHARS] + "\n... (truncated)"
    return result


def _marts_only_rules(project: str, marts: str, marts_ads: str) -> str:
    """Rules for Copilot: ONLY fct_sessions and fct_ad_spend. Channel error message."""
    return f"""

## Allowed tables only
- **hypeon_marts.fct_sessions** — event/session/product views (event_name, item_id, utm_source, device).
- **hypeon_marts_ads.fct_ad_spend** — ad performance (channel, cost, clicks, conversions). Use for campaign/channel questions.
- Do NOT reference ads_daily_staging, ga4_daily_staging, analytics_cache, decision_store, or raw datasets.

## Query behavior (user intent -> SQL)
| User intent       | SQL behavior |
| views / item views| event_name IN ('view_item','view_item_list'), item_id LIKE 'prefix%' in fct_sessions |
| item views from Google | Same as above + utm_source LIKE '%google%' (or LOWER(utm_source) LIKE '%google%') in fct_sessions |
| google traffic    | utm_source LIKE '%google%' in fct_sessions |
| channel / ad spend| Query fct_ad_spend; filter by channel. |

## Important: date filter for fct_sessions (required)
- You MUST add a date filter to every query that uses fct_sessions (item views, traffic, "from Google", etc.). Without it the query may exceed the bytes limit and fail. Use: WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) (or INTERVAL 7 DAY for last week). If the table has event_date, use event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) instead. Add this filter even when the user does not ask for a date range.

## Unavailable channel (e.g. Facebook)
- If the user asks for a channel (e.g. "views from Facebook", "Facebook traffic") that is NOT in the data:
  - First check: SELECT DISTINCT channel FROM `{project}.{marts_ads}.fct_ad_spend` (or from schema: channel column).
  - If the requested channel (e.g. facebook) is not present, respond with exactly:
    "[Channel] channel data is not currently present in the dataset. Available channels: google_ads. Once [Channel] data is integrated, this query will be supported."
  - Do NOT mention staging tables, raw tables, or analytics_cache.

## Query guidelines
- Use only SELECT. Table names: `{project}.{marts}.fct_sessions`, `{project}.{marts_ads}.fct_ad_spend`.
- Filter by date when relevant.
"""


def get_raw_schema_for_copilot() -> str:
    """
    Load raw_copilot_schema.json and return a string for the system prompt (run_sql_raw fallback).
    If file is missing or empty, returns a short message to use marts only. Capped at _RAW_SCHEMA_MAX_CHARS.
    """
    path = _raw_schema_path()
    if not path.is_file():
        return "Raw data schema not available; use marts only (run_sql)."
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "Raw data schema not available; use marts only."
    if not isinstance(data, dict):
        return "Raw data schema not available; use marts only."
    project = data.get("project") or get_bq_source_project()
    hints = (data.get("hints") or "").strip()
    datasets = data.get("datasets") or {}
    parts = [
        "",
        "## Fallback: raw data (run_sql_raw)",
        "Use run_sql_raw only when marts (run_sql) don't have the needed data or returned no rows.",
        "Allowed: GA4 events_* tables, Ads ads_AccountBasicStats_* tables. Always include LIMIT and, for GA4, a date filter (event_date).",
        "",
    ]
    if hints:
        parts.append(f"Query hints: {hints}")
        parts.append("")
    for ds_id, ds_obj in sorted(datasets.items()):
        if not isinstance(ds_obj, dict):
            continue
        tables = ds_obj.get("tables") or {}
        for table_id, table_info in sorted(tables.items()):
            if not isinstance(table_info, dict):
                continue
            schema = table_info.get("schema") or []
            sample_rows = table_info.get("sample_rows") or []
            flat = _flatten_schema(schema)
            col_list = ", ".join(f"{n} ({t})" for n, t in flat[:40])
            if len(flat) > 40:
                col_list += f", ... and {len(flat) - 40} more"
            parts.append(f"- **{ds_id}.{table_id}** (project: {project})")
            parts.append(f"  Columns: {col_list}")
            for i, row in enumerate(sample_rows[:2]):
                if isinstance(row, dict):
                    snippet = json.dumps(row, default=str)[:400]
                    parts.append(f"  Sample {i + 1}: {snippet}")
            parts.append("")
    result = "\n".join(parts).strip()
    if len(result) > _RAW_SCHEMA_MAX_CHARS:
        result = result[:_RAW_SCHEMA_MAX_CHARS] + "\n... (truncated)"
    return result if result else "Raw data schema not available; use marts only."
