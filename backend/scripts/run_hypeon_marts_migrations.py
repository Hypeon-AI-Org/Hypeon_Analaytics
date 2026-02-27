#!/usr/bin/env python3
"""
Run hypeon_marts SQL migrations. Substitutes BQ_PROJECT, BQ_SOURCE_PROJECT, BQ_LOCATION, GA4_DATASET, ADS_DATASET from .env.
Uses BQ_LOCATION (europe-north2) so jobs can access GA4 (europe-north2) and Ads (EU).
If hypeon_marts was already created in US, delete it in BigQuery console and re-run so it is created in BQ_LOCATION.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(_repo_root / ".env")

BQ_PROJECT = os.environ.get("BQ_PROJECT", "hypeon-ai-prod")
BQ_SOURCE_PROJECT = os.environ.get("BQ_SOURCE_PROJECT") or BQ_PROJECT
BQ_LOCATION = os.environ.get("BQ_LOCATION", "europe-north2")  # GA4 analytics_444259275
BQ_LOCATION_ADS = os.environ.get("BQ_LOCATION_ADS", "EU")  # Ads 146568
GA4_DATASET = os.environ.get("GA4_DATASET", "analytics_444259275")
ADS_DATASET = os.environ.get("ADS_DATASET", "146568")

MART_SQL_DIR = _repo_root / "bq_sql" / "hypeon_marts"
# GA4 (europe-north2) first; then Ads (EU) in separate dataset hypeon_marts_ads
ORDER_GA4 = [
    "00_create_dataset.sql",
    "01_stg_ga4__events.sql",
    "03_int_sessions.sql",
    "04_fct_sessions.sql",
]
ORDER_ADS = [
    "00_create_dataset_ads.sql",
    "02_stg_google_ads__performance.sql",
    "05_fct_ad_spend.sql",
]


def main() -> None:
    from google.cloud import bigquery
    # Job/dataset location must be EU region to access 146568 (EU) and analytics_444259275 (europe-north2)
    client = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION)
    # From scratch: drop both marts so they are recreated
    drop_first = os.environ.get("DROP_MARTS_FIRST", "").strip().lower() in ("1", "true", "yes")
    if drop_first:
        for name in ["hypeon_marts", "hypeon_marts_ads"]:
            try:
                ds = client.get_dataset(f"{BQ_PROJECT}.{name}")
                print(f"Dropping {name} (location: {ds.location or '?'}) for from-scratch recreate ...")
                client.delete_dataset(ds, delete_contents=True)
            except Exception:
                pass
    else:
        try:
            ds = client.get_dataset(f"{BQ_PROJECT}.hypeon_marts")
            ds_loc = (ds.location or "").lower()
            want_loc = BQ_LOCATION.lower()
            if ds_loc != want_loc:
                print(f"Dataset hypeon_marts exists in '{ds_loc}' but BQ_LOCATION is '{BQ_LOCATION}'.")
                print("Delete it in BigQuery console or run with DROP_MARTS_FIRST=1 to drop and recreate, then re-run.")
                return
        except Exception:
            pass
    subs = {
        "{BQ_PROJECT}": BQ_PROJECT,
        "{BQ_SOURCE_PROJECT}": BQ_SOURCE_PROJECT,
        "{BQ_LOCATION}": BQ_LOCATION,
        "{BQ_LOCATION_ADS}": BQ_LOCATION_ADS,
        "{GA4_DATASET}": GA4_DATASET,
        "{ADS_DATASET}": ADS_DATASET,
    }

    def run_order(order: list[str], bq_client) -> None:
        for name in order:
            path = MART_SQL_DIR / name
            if not path.exists():
                continue
            sql = path.read_text(encoding="utf-8")
            for k, v in subs.items():
                sql = sql.replace(k, v)
            lines = [l for l in sql.split("\n") if not l.strip().startswith("--")]
            stmt = "\n".join(lines).strip().rstrip(";").strip()
            if not stmt:
                continue
            print(f"Running {name} ...")
            job = bq_client.query(stmt)
            job.result()
            print(f"  OK: {name}")

    run_order(ORDER_GA4, client)
    client_ads = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION_ADS)
    run_order(ORDER_ADS, client_ads)
    print("hypeon_marts (GA4) + hypeon_marts_ads (Ads) migrations done.")


if __name__ == "__main__":
    main()
