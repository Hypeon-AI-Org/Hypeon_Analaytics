#!/usr/bin/env python3
"""
Diagnose why Copilot schema load fails. Run from repo root:
  python scripts/diagnose_copilot_schema.py
Or from backend with app on path:
  python -c "from app.clients.bigquery import get_marts_schema_live; ..."
Prints the actual BigQuery error instead of swallowing it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env from repo root
_repo_root = Path(__file__).resolve().parents[1]
_env = _repo_root / ".env"
if _env.is_file():
    from dotenv import load_dotenv
    load_dotenv(_env)

# Ensure backend app is importable
_backend = _repo_root / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

os.chdir(str(_backend))


def main() -> int:
    project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
    marts = os.environ.get("MARTS_DATASET", "hypeon_marts")
    marts_ads = os.environ.get("MARTS_ADS_DATASET", "hypeon_marts_ads")
    location = os.environ.get("BQ_LOCATION", "europe-north2")
    location_ads = os.environ.get("BQ_LOCATION_ADS", "EU")

    print("Diagnosing Copilot schema load (get_marts_schema_live)...")
    print(f"  BQ_PROJECT={project}")
    print(f"  MARTS_DATASET={marts}, MARTS_ADS_DATASET={marts_ads}")
    print(f"  BQ_LOCATION={location}, BQ_LOCATION_ADS={location_ads}")
    print()

    try:
        from google.cloud import bigquery
    except ImportError as e:
        print("ERROR: google-cloud-bigquery not installed:", e)
        return 1

    for ds, loc in [(marts, location), (marts_ads, location_ads)]:
        q = f"SELECT table_name, column_name FROM `{project}.{ds}.INFORMATION_SCHEMA.COLUMNS` ORDER BY table_name, ordinal_position"
        print(f"Query: {project}.{ds}.INFORMATION_SCHEMA.COLUMNS (location={loc})")
        try:
            client = bigquery.Client(project=project, location=loc)
            df = client.query(q).to_dataframe()
            print(f"  -> OK: {len(df)} rows")
        except Exception as e:
            print(f"  -> FAIL: {type(e).__name__}: {e}")
            return 1

    print()
    print("Schema load would succeed. If Copilot still shows 'schema could not be loaded', clear the in-process cache by restarting the backend.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
