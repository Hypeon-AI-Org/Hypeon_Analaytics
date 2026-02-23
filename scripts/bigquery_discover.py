#!/usr/bin/env python3
"""
Discover BigQuery dataset structure: datasets, tables, columns (names and types).
Use this to understand your data before designing backend ingest for Google Ads and Google Analytics.

Uses GOOGLE_APPLICATION_CREDENTIALS (path to service account key JSON) from env or .env.

Usage:
  # List all datasets in project, then all tables and columns
  python scripts/bigquery_discover.py --project YOUR_GCP_PROJECT_ID

  # Single dataset only
  python scripts/bigquery_discover.py --project YOUR_GCP_PROJECT_ID --dataset your_dataset_id

  # Both Google Ads and Google Analytics datasets (writes combined + per-source files)
  python scripts/bigquery_discover.py --project YOUR_GCP_PROJECT_ID \\
    --google-ads-dataset YOUR_GOOGLE_ADS_DATASET_ID \\
    --google-analytics-dataset YOUR_GA_DATASET_ID \\
    --output-dir ./bigquery_schema

  # Multiple datasets by ID
  python scripts/bigquery_discover.py --project YOUR_GCP_PROJECT_ID --datasets ds1 ds2

  # Write results to files (JSON + Markdown)
  python scripts/bigquery_discover.py --project YOUR_GCP_PROJECT_ID --output-dir ./bigquery_schema

  # Skip row counts and sample rows (faster)
  python scripts/bigquery_discover.py --project YOUR_GCP_PROJECT_ID --no-stats

Requires: pip install google-cloud-bigquery
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _import_bigquery():
    try:
        from google.cloud import bigquery
        return bigquery
    except ImportError as e:
        print("google-cloud-bigquery is not installed. Install with:", file=sys.stderr)
        print("  pip install google-cloud-bigquery", file=sys.stderr)
        sys.exit(1)


def _field_to_dict(field) -> dict:
    """Convert BigQuery SchemaField to a serializable dict."""
    d = {"name": field.name, "type": field.field_type, "mode": field.mode or "NULLABLE"}
    if field.fields:
        d["fields"] = [_field_to_dict(f) for f in field.fields]
    return d


def get_table_schema(client, full_table_id: str) -> list[dict]:
    """Return list of column dicts (name, type, mode) for the table."""
    table = client.get_table(full_table_id)
    return [_field_to_dict(f) for f in table.schema]


def get_row_count(client, full_table_id: str) -> int | None:
    """Return approximate or exact row count. Returns None on error."""
    try:
        q = client.query(f"SELECT COUNT(*) AS n FROM `{full_table_id}`")
        return next(q.result()).n
    except Exception:
        return None


def get_sample_row(client, full_table_id: str) -> dict | None:
    """Return one row as a dict (values as strings for JSON). Returns None on error or empty table."""
    try:
        q = client.query(f"SELECT * FROM `{full_table_id}` LIMIT 1")
        row = next(q.result(), None)
        if row is None:
            return None
        return {k: str(v) if v is not None else None for k, v in row.items()}
    except Exception:
        return None


def discover_datasets(client, project: str) -> list[str]:
    """List all dataset IDs in the project."""
    ids = []
    for ds in client.list_datasets(project=project):
        ids.append(ds.dataset_id)
    return sorted(ids)


def discover_tables(client, project: str, dataset_id: str) -> list[str]:
    """List all table IDs in the dataset."""
    full_dataset = f"{project}.{dataset_id}"
    ids = []
    for t in client.list_tables(full_dataset):
        ids.append(t.table_id)
    return sorted(ids)


def run_discovery(
    project: str,
    dataset_id: str | None,
    dataset_ids_arg: list[str] | None = None,
    include_stats: bool = True,
) -> dict:
    """Run full discovery. Returns a dict: datasets -> tables -> { schema, row_count?, sample_row? }."""
    bigquery = _import_bigquery()
    client = bigquery.Client(project=project)

    if dataset_ids_arg:
        dataset_ids = dataset_ids_arg
    elif dataset_id:
        dataset_ids = [dataset_id]
    else:
        dataset_ids = discover_datasets(client, project)
        if not dataset_ids:
            return {"project": project, "datasets": {}, "message": "No datasets found in project."}

    result = {"project": project, "datasets": {}}

    for ds_id in dataset_ids:
        result["datasets"][ds_id] = {"tables": {}}
        try:
            table_ids = discover_tables(client, project, ds_id)
        except Exception as e:
            result["datasets"][ds_id]["error"] = str(e)
            continue

        for table_id in table_ids:
            full_id = f"{project}.{ds_id}.{table_id}"
            entry = {}
            try:
                entry["schema"] = get_table_schema(client, full_id)
            except Exception as e:
                entry["error"] = str(e)
                result["datasets"][ds_id]["tables"][table_id] = entry
                continue

            if include_stats:
                entry["row_count"] = get_row_count(client, full_id)
                entry["sample_row"] = get_sample_row(client, full_id)

            result["datasets"][ds_id]["tables"][table_id] = entry

    return result


def print_summary(data: dict) -> None:
    """Print human-readable summary to stdout."""
    print(f"Project: {data['project']}")
    if "message" in data:
        print(data["message"])
        return
    for ds_id, ds_info in data["datasets"].items():
        print(f"\nDataset: {ds_id}")
        if "error" in ds_info:
            print(f"  Error: {ds_info['error']}")
            continue
        tables = ds_info.get("tables", {})
        for table_id, tbl in tables.items():
            print(f"  Table: {table_id}")
            if "error" in tbl:
                print(f"    Error: {tbl['error']}")
                continue
            schema = tbl.get("schema", [])
            for col in schema:
                name = col.get("name", "?")
                typ = col.get("type", "?")
                mode = col.get("mode", "")
                print(f"    - {name}: {typ} ({mode})")
            if "row_count" in tbl and tbl["row_count"] is not None:
                print(f"    Row count: {tbl['row_count']}")
            if tbl.get("sample_row"):
                print(f"    Sample: {tbl['sample_row']}")


def _schema_rows(schema: list[dict], prefix: str = "") -> list[tuple[str, str, str]]:
    """Flatten schema to (name, type, mode) including nested RECORD fields."""
    rows = []
    for col in schema:
        name = prefix + col.get("name", "?")
        typ = col.get("type", "?")
        mode = col.get("mode", "?")
        rows.append((name, typ, mode))
        if col.get("fields"):
            for sub in _schema_rows(col["fields"], prefix=name + "."):
                rows.append(sub)
    return rows


def to_markdown(data: dict) -> str:
    """Return a Markdown report of the discovery."""
    lines = [f"# BigQuery discovery: {data['project']}", ""]
    if "message" in data:
        lines.append(data["message"])
        return "\n".join(lines)
    for ds_id, ds_info in data["datasets"].items():
        lines.append(f"## Dataset: `{ds_id}`")
        lines.append("")
        if "error" in ds_info:
            lines.append(f"Error: {ds_info['error']}")
            lines.append("")
            continue
        for table_id, tbl in ds_info.get("tables", {}).items():
            lines.append(f"### Table: `{table_id}`")
            if "error" in tbl:
                lines.append(f"- Error: {tbl['error']}")
                lines.append("")
                continue
            lines.append("| Column | Type | Mode |")
            lines.append("|--------|------|------|")
            for name, typ, mode in _schema_rows(tbl.get("schema", [])):
                lines.append(f"| {name} | {typ} | {mode} |")
            if "row_count" in tbl and tbl["row_count"] is not None:
                lines.append(f"- **Row count:** {tbl['row_count']}")
            if tbl.get("sample_row"):
                lines.append("- **Sample row:**")
                for k, v in tbl["sample_row"].items():
                    lines.append(f"  - `{k}`: `{v}`")
            lines.append("")
    return "\n".join(lines)


def _load_dotenv() -> None:
    """Load .env from project root so GOOGLE_APPLICATION_CREDENTIALS can be set there."""
    try:
        from pathlib import Path
        import os
        script_dir = Path(__file__).resolve().parent
        for d in [script_dir, script_dir.parent]:
            env_file = d / ".env"
            if env_file.exists():
                from dotenv import load_dotenv
                load_dotenv(env_file)
                break
    except ImportError:
        pass


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(
        description="Discover BigQuery datasets, tables, and column schemas."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="GCP project ID",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Optional: single dataset ID. If omitted, list all datasets in project.",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=None,
        metavar="ID",
        help="Optional: list of dataset IDs (e.g. --datasets google_ads_ds ga_ds). Overrides --dataset.",
    )
    parser.add_argument(
        "--google-ads-dataset",
        default=None,
        metavar="ID",
        help="Google Ads BigQuery dataset ID. Use with --google-analytics-dataset to discover both and write per-source files.",
    )
    parser.add_argument(
        "--google-analytics-dataset",
        default=None,
        metavar="ID",
        help="Google Analytics BigQuery dataset ID. Use with --google-ads-dataset to discover both and write per-source files.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        type=Path,
        help="Optional: write discovery JSON and Markdown report here.",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Skip row count and sample row (faster).",
    )
    args = parser.parse_args()

    # Resolve dataset list: --datasets > (--google-ads-dataset + --google-analytics-dataset) > --dataset > all
    dataset_ids_arg = args.datasets
    if dataset_ids_arg is None and (args.google_ads_dataset or args.google_analytics_dataset):
        dataset_ids_arg = []
        if args.google_ads_dataset:
            dataset_ids_arg.append(args.google_ads_dataset)
        if args.google_analytics_dataset:
            dataset_ids_arg.append(args.google_analytics_dataset)

    data = run_discovery(
        project=args.project,
        dataset_id=args.dataset,
        dataset_ids_arg=dataset_ids_arg,
        include_stats=not args.no_stats,
    )

    print_summary(data)

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = args.output_dir / "bigquery_discovery.json"
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"\nWrote {json_path}")
        md_path = args.output_dir / "bigquery_discovery.md"
        md_path.write_text(to_markdown(data), encoding="utf-8")
        print(f"Wrote {md_path}")

        # Per-source files when Google Ads and/or Google Analytics datasets are specified
        labels = []
        if args.google_ads_dataset:
            labels.append(("google_ads", args.google_ads_dataset))
        if args.google_analytics_dataset:
            labels.append(("google_analytics", args.google_analytics_dataset))
        for source_label, ds_id in labels:
            if ds_id not in data.get("datasets", {}):
                continue
            subset = {
                "project": data["project"],
                "datasets": {ds_id: data["datasets"][ds_id]},
                "source": source_label,
            }
            out_json = args.output_dir / f"bigquery_discovery_{source_label}.json"
            out_md = args.output_dir / f"bigquery_discovery_{source_label}.md"
            out_json.write_text(json.dumps(subset, indent=2), encoding="utf-8")
            out_md.write_text(to_markdown(subset), encoding="utf-8")
            print(f"Wrote {out_json}")
            print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
