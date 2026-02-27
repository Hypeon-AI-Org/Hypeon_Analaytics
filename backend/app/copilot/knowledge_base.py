"""
Knowledge base for Copilot: live schema from hypeon_marts.INFORMATION_SCHEMA (primary);
fallback to bigquery_schema/bigquery_discovery.json for raw ADS_DATASET/GA4_DATASET.
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
    Return schema for the LLM: live from hypeon_marts.INFORMATION_SCHEMA.COLUMNS when available;
    otherwise from bigquery_discovery.json (ADS_DATASET, GA4_DATASET). Includes GA4 rules and query behavior.
    """
    global _SCHEMA_CACHE
    if use_cache and _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    project = get_bq_project()
    source_project = get_bq_source_project()
    ads_ds = get_ads_dataset().strip()
    ga4_ds = get_ga4_dataset().strip()
    marts_ds = get_marts_dataset().strip()

    # Prefer live marts schema
    try:
        from ..clients.bigquery import get_marts_schema_live
        live_rows = get_marts_schema_live()
        if live_rows:
            schema_text = _format_live_marts_schema(live_rows, project, marts_ds)
            schema_text += _ga4_and_query_rules(project, marts_ds, source_project, ga4_ds, ads_ds)
            _SCHEMA_CACHE = schema_text
            return schema_text
    except Exception:
        pass

    # Fallback: discovery file for raw datasets
    allowed_dataset_ids = {ads_ds.lower(), ga4_ds.lower(), marts_ds.lower()}
    discovery_path = _discovery_path()
    if not discovery_path.is_file():
        fallback = _fallback_schema(project, source_project, ads_ds, ga4_ds, reason="Discovery file not found.")
        fallback += _ga4_and_query_rules(project, marts_ds, source_project, ga4_ds, ads_ds)
        _SCHEMA_CACHE = fallback
        return fallback

    try:
        raw = discovery_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as e:
        fallback = _fallback_schema(project, source_project, ads_ds, ga4_ds, reason=f"Discovery load error: {e!s}.")
        fallback += _ga4_and_query_rules(project, marts_ds, source_project, ga4_ds, ads_ds)
        _SCHEMA_CACHE = fallback
        return fallback

    datasets = data.get("datasets") or {}
    if not isinstance(datasets, dict):
        fallback = _fallback_schema(project, source_project, ads_ds, ga4_ds, reason="Invalid discovery.")
        fallback += _ga4_and_query_rules(project, marts_ds, source_project, ga4_ds, ads_ds)
        _SCHEMA_CACHE = fallback
        return fallback

    parts = [
        "## Database: BigQuery (read-only)",
        f"- Project: {project}. Marts: {marts_ds}. Ads: {ads_ds}. GA4: {ga4_ds}.",
        "- Use backtick-quoted full names: `project.dataset.table`.",
        "",
        "## Tables and columns (from discovery)",
        "",
    ]
    total_len = sum(len(p) for p in parts)
    for ds_id, ds_info in sorted(datasets.items()):
        if ds_id.strip().lower() not in allowed_dataset_ids:
            continue
        if not isinstance(ds_info, dict):
            continue
        tables = ds_info.get("tables") or {}
        if not isinstance(tables, dict):
            continue
        parts.append(f"### Dataset: {ds_id}\n")
        for table_id, tbl in sorted(tables.items()):
            if total_len >= _SCHEMA_MAX_CHARS:
                parts.append("... (truncated)")
                break
            if not isinstance(tbl, dict):
                continue
            schema_list = tbl.get("schema")
            if not schema_list and "error" in tbl:
                parts.append(f"- **{table_id}**: (error)")
                continue
            flat = _flatten_schema(schema_list) if schema_list else []
            col_lines = [f"  - {name}: {typ}" for name, typ in flat[:80]]
            if len(flat) > 80:
                col_lines.append(f"  - ... +{len(flat) - 80} more")
            parts.append(f"- **{table_id}**\n" + "\n".join(col_lines) + "\n")
            total_len += len(parts[-1])
        if total_len >= _SCHEMA_MAX_CHARS:
            break
    schema_text = "\n".join(parts) + _ga4_and_query_rules(project, marts_ds, source_project, ga4_ds, ads_ds)
    samples_section = _load_samples_section()
    if samples_section and len(schema_text) + len(samples_section) < _SCHEMA_MAX_CHARS:
        schema_text = schema_text + samples_section
    _SCHEMA_CACHE = schema_text
    return schema_text


def _ga4_and_query_rules(project: str, marts: str, source_project: str, ga4_ds: str, ads_ds: str) -> str:
    """GA4 rules and query behavior for Copilot (system knowledge)."""
    return f"""

## GA4 rules (mandatory)
- GA4 uses nested schema. Product data lives in UNNEST(items) AS item; item_id = item.item_id.
- Views = event_name = 'view_item' (or 'view_item_list'). Clicks = event_name = 'select_item'. Purchase = event_name = 'purchase'.
- Traffic source = traffic_source.source (e.g. utm_source in marts). For "from Google" use utm_source LIKE '%google%' or LOWER(utm_source) = 'google'.
- If you reference item_id in a query and the table is GA4 raw events_*, you MUST use UNNEST(COALESCE(items, [])) AS item and item.item_id. Never use item_id without UNNEST(items) on raw GA4.

## Query behavior (user intent -> SQL)
| User intent       | SQL behavior |
| views             | event_name='view_item' (or view_item_list) |
| clicks            | event_name='select_item' |
| purchase          | event_name='purchase' |
| item prefix       | item_id LIKE 'XXX%' or STARTS_WITH(item_id, 'XXX') |
| google traffic    | utm_source LIKE '%google%' |
- Prefer hypeon_marts.fct_sessions and hypeon_marts.fct_ad_spend for analytics. Use `{project}.{marts}.table_name`.

## Query guidelines
- Use only SELECT (or WITH ... SELECT). No INSERT/UPDATE/DELETE/DROP.
- Table names: backtick-quoted. For marts: `{project}.{marts}.fct_sessions`, `{project}.{marts}.fct_ad_spend`, etc.
- Filter by event_date or date when relevant to limit scan.
"""


def _fallback_schema(project: str, source_project: str, ads_ds: str, ga4_ds: str, reason: str) -> str:
    """Short fallback when discovery is unavailable."""
    return f"""## Database: BigQuery (read-only for Copilot)
- Project: {project}. Source project (GA4 raw): {source_project}.
- Ads dataset (ADS_DATASET): {ads_ds}. GA4 dataset (GA4_DATASET): {ga4_ds}.
- {reason}
- You may query any table in these two datasets. Use backtick-quoted names: `project.dataset.table`. For GA4 events use `{source_project}.{ga4_ds}.events_*`.
- Always use SELECT only. Scope by client_id/customer_id when the column exists; for events_* filter by event_date and event_name/items.
## Data semantics
- Item ID / product views: GA4 events_* only. Use event_name IN ('view_item','view_item_list'), UNNEST(COALESCE(items,[])) AS it, it.item_id. Not in Ads (campaign_id/ad_group_id are not item IDs).
- Traffic source (from Google etc.): GA4 traffic_source.source; filter with LOWER(traffic_source.source) LIKE '%google%'.
- Campaign/ad spend and ROAS: Ads dataset (ads_*), not GA4.
"""
