"""
Knowledge base for Copilot: schema of RAW datasets only (ADS_DATASET, GA4_DATASET).
Built from bigquery_schema/bigquery_discovery.json so the LLM can generate correct SQL via run_sql.
Optional: bigquery_schema/copilot_samples.json for sample rows (see scripts/copilot_fetch_samples.py).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# In-process cache for get_schema_for_copilot() to avoid re-reading discovery on every request.
_SCHEMA_CACHE: str | None = None


def get_bq_project() -> str:
    return os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")


def get_bq_source_project() -> str:
    """Project where GA4 raw events live (BQ_SOURCE_PROJECT or BQ_PROJECT)."""
    return os.environ.get("BQ_SOURCE_PROJECT") or get_bq_project()


def get_analytics_dataset() -> str:
    return os.environ.get("ANALYTICS_DATASET", "analytics")


def get_ads_dataset() -> str:
    """Dataset for Ads (from .env ADS_DATASET, e.g. 146568). Copilot queries any table in this dataset."""
    return os.environ.get("ADS_DATASET", "146568")


def get_ga4_dataset() -> str:
    """Dataset for GA4 (from .env GA4_DATASET, e.g. analytics_444259275). Copilot queries any table including events_*."""
    return os.environ.get("GA4_DATASET", "analytics_444259275")


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


def get_schema_for_copilot(use_cache: bool = True) -> str:
    """
    Return schema description for the LLM: all tables in ADS_DATASET and GA4_DATASET
    from bigquery_discovery.json. If file is missing or invalid, returns a short fallback.
    Optionally appends sample rows from copilot_samples.json. Result is cached in-process.
    """
    global _SCHEMA_CACHE
    if use_cache and _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    project = get_bq_project()
    source_project = get_bq_source_project()
    ads_ds = get_ads_dataset().strip()
    ga4_ds = get_ga4_dataset().strip()
    allowed_dataset_ids = {ads_ds.lower(), ga4_ds.lower()}

    discovery_path = _discovery_path()
    if not discovery_path.is_file():
        fallback = _fallback_schema(project, source_project, ads_ds, ga4_ds, reason="Discovery file not found.")
        _SCHEMA_CACHE = fallback
        return fallback

    try:
        raw = discovery_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as e:
        fallback = _fallback_schema(project, source_project, ads_ds, ga4_ds, reason=f"Discovery load error: {e!s}.")
        _SCHEMA_CACHE = fallback
        return fallback

    datasets = data.get("datasets") or {}
    if not isinstance(datasets, dict):
        fallback = _fallback_schema(project, source_project, ads_ds, ga4_ds, reason="Invalid discovery: datasets not a dict.")
        _SCHEMA_CACHE = fallback
        return fallback

    parts: list[str] = [
        "## Database: BigQuery (read-only for Copilot)",
        f"- Project: {project} (and source {source_project} for GA4 raw if set).",
        f"- Ads dataset (ADS_DATASET): {ads_ds}. GA4 dataset (GA4_DATASET): {ga4_ds}.",
        "- You may query ANY table in these two datasets. Use backtick-quoted full names: `project.dataset.table`.",
        f"- For GA4 daily event tables use wildcard: `{source_project}.{ga4_ds}.events_*`.",
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
        parts.append(f"### Dataset: {ds_id}")
        parts.append("")
        for table_id, tbl in sorted(tables.items()):
            if total_len >= _SCHEMA_MAX_CHARS:
                parts.append("... (schema truncated for length)")
                break
            if not isinstance(tbl, dict):
                continue
            schema_list = tbl.get("schema")
            if not schema_list and "error" in tbl:
                parts.append(f"- **{table_id}**: (schema error: {tbl['error'][:80]})")
                total_len += len(parts[-1])
                continue
            flat = _flatten_schema(schema_list) if schema_list else []
            col_lines = [f"  - {name}: {typ}" for name, typ in flat[:80]]  # cap columns per table
            if len(flat) > 80:
                col_lines.append(f"  - ... and {len(flat) - 80} more columns")
            table_block = f"- **{table_id}**\n" + "\n".join(col_lines)
            if total_len + len(table_block) + 2 > _SCHEMA_MAX_CHARS:
                parts.append(table_block[: _SCHEMA_MAX_CHARS - total_len - 20] + "\n... (truncated)")
                total_len = _SCHEMA_MAX_CHARS
                break
            parts.append(table_block)
            parts.append("")
            total_len += len(table_block) + 2
        if total_len >= _SCHEMA_MAX_CHARS:
            break
        parts.append("")

    parts.append("## Query guidelines")
    parts.append("- Use only SELECT (or WITH ... SELECT). No INSERT/UPDATE/DELETE/DROP.")
    parts.append("- For tables that have client_id / customer_id: filter by the current client when relevant.")
    parts.append("- For GA4 events_*: filter by event_date (e.g. event_date >= '20240101') to limit scan; use event_name, UNNEST(COALESCE(items,[])) for item-level; UNNEST(event_params) for params.")
    parts.append("- Table names must be backtick-quoted: `project.dataset.table`.")
    parts.append("")
    parts.append("## Data semantics (choose the right dataset)")
    parts.append("- **Item ID, product ID, item views, product views**: GA4 only. Query `events_*` with event_name IN ('view_item','view_item_list') and UNNEST(COALESCE(items,[])) AS it, then it.item_id. Use STARTS_WITH(it.item_id, 'prefix') or LIKE for prefix. Do NOT use Ads tables (campaign_id, ad_group_id are campaign/ad identifiers, not product/item IDs).")
    parts.append("- **Traffic source (from Google, from Facebook, etc.)**: GA4 events have traffic_source.source (string). For session-level use session_traffic_source_last_click.manual_campaign.source or .cross_channel_campaign.source. Filter with LOWER(COALESCE(traffic_source.source,'')) LIKE '%google%' for 'from Google', or LIKE '%facebook%' for 'from Facebook'.")
    parts.append("- **Campaign/ad performance (spend, revenue, ROAS, clicks)**: Ads dataset (ads_* tables) with customer_id. GA4 events_* are for site/app events (sessions, item views, conversions), not ad spend.")
    schema_text = "\n".join(parts)
    samples_section = _load_samples_section()
    if samples_section and len(schema_text) + len(samples_section) < _SCHEMA_MAX_CHARS:
        schema_text = schema_text + samples_section
    _SCHEMA_CACHE = schema_text
    return schema_text


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
