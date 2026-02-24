#!/usr/bin/env python3
"""
Run the unified marketing_performance_daily table via two-region pipeline:
1. Ads-only job in EU (source 146568 is in EU) -> staging_eu.ads_daily_staging
2. Copy ads_daily_staging from EU to analytics.ads_daily_staging (europe-north2)
3. GA4-only job in europe-north2 -> analytics.ga4_daily_staging
4. Union job in europe-north2 -> marketing_performance_daily

Uses env: BQ_PROJECT, BQ_SOURCE_PROJECT, BQ_LOCATION (GA4 region), BQ_LOCATION_ADS (EU),
ANALYTICS_DATASET, STAGING_EU_DATASET, ADS_DATASET, GA4_DATASET.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend app to path if running from repo root
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env from repo root so BQ_PROJECT etc. are set when run from CLI
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

BQ_PROJECT = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
BQ_SOURCE_PROJECT = os.environ.get("BQ_SOURCE_PROJECT") or BQ_PROJECT
# GA4 and final table region
BQ_LOCATION = os.environ.get("BQ_LOCATION", "europe-north2")
# Ads source is in EU
BQ_LOCATION_ADS = os.environ.get("BQ_LOCATION_ADS", "EU")
ANALYTICS_DATASET = os.environ.get("ANALYTICS_DATASET", "analytics")
STAGING_EU_DATASET = os.environ.get("STAGING_EU_DATASET", "staging_eu")
ADS_DATASET = os.environ.get("ADS_DATASET", "146568")
GA4_DATASET = os.environ.get("GA4_DATASET", "analytics_444259275")

SQL_ADS = ROOT / "bq_sql" / "create_unified_table_ads_only.sql"
SQL_GA4 = ROOT / "bq_sql" / "create_unified_table_ga4_only.sql"
SQL_UNION = ROOT / "bq_sql" / "create_unified_table_union.sql"


def ensure_staging_eu_dataset(client_eu):
    """Create staging_eu dataset in EU if it does not exist."""
    from google.cloud import bigquery
    dataset_ref = bigquery.DatasetReference(BQ_PROJECT, STAGING_EU_DATASET)
    try:
        client_eu.get_dataset(dataset_ref)
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = BQ_LOCATION_ADS
        client_eu.create_dataset(dataset)
        print(f"Created dataset {BQ_PROJECT}.{STAGING_EU_DATASET} in {BQ_LOCATION_ADS}")


def main() -> int:
    try:
        from google.cloud import bigquery
    except ImportError:
        print("Install google-cloud-bigquery: pip install google-cloud-bigquery", file=sys.stderr)
        return 1

    if not SQL_ADS.exists() or not SQL_GA4.exists() or not SQL_UNION.exists():
        print("SQL files not found", file=sys.stderr)
        return 1

    # Clients: one for EU (Ads), one for europe-north2 (GA4 + union)
    client_ads = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION_ADS)
    client_main = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION)

    # 1) Ensure staging_eu exists, then run Ads-only job in EU
    ensure_staging_eu_dataset(client_ads)
    sql_ads = SQL_ADS.read_text()
    for k, v in [
        ("{BQ_PROJECT}", BQ_PROJECT),
        ("{BQ_SOURCE_PROJECT}", BQ_SOURCE_PROJECT),
        ("{ADS_DATASET}", ADS_DATASET),
        ("{STAGING_EU_DATASET}", STAGING_EU_DATASET),
    ]:
        sql_ads = sql_ads.replace(k, v)
    print(f"Running Ads-only job in {BQ_LOCATION_ADS}...")
    job_ads = client_ads.query(sql_ads)
    job_ads.result()
    print(f"  -> {BQ_PROJECT}.{STAGING_EU_DATASET}.ads_daily_staging")

    # 2) Copy ads_daily_staging from EU to analytics (europe-north2)
    source_ref = bigquery.TableReference(
        bigquery.DatasetReference(BQ_PROJECT, STAGING_EU_DATASET), "ads_daily_staging"
    )
    dest_ref = bigquery.TableReference(
        bigquery.DatasetReference(BQ_PROJECT, ANALYTICS_DATASET), "ads_daily_staging"
    )
    print(f"Copying ads_daily_staging to {BQ_LOCATION}...")
    copy_config = bigquery.CopyJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    copy_job = client_ads.copy_table(source_ref, dest_ref, job_config=copy_config)
    copy_job.result()
    print(f"  -> {BQ_PROJECT}.{ANALYTICS_DATASET}.ads_daily_staging")

    # 3) GA4-only job in europe-north2
    sql_ga4 = SQL_GA4.read_text()
    for k, v in [
        ("{BQ_PROJECT}", BQ_PROJECT),
        ("{BQ_SOURCE_PROJECT}", BQ_SOURCE_PROJECT),
        ("{GA4_DATASET}", GA4_DATASET),
        ("{ANALYTICS_DATASET}", ANALYTICS_DATASET),
    ]:
        sql_ga4 = sql_ga4.replace(k, v)
    print(f"Running GA4-only job in {BQ_LOCATION}...")
    job_ga4 = client_main.query(sql_ga4)
    job_ga4.result()
    print(f"  -> {BQ_PROJECT}.{ANALYTICS_DATASET}.ga4_daily_staging")

    # 4) Union and build final table in europe-north2
    sql_union = SQL_UNION.read_text()
    sql_union = sql_union.replace("{BQ_PROJECT}", BQ_PROJECT).replace("{ANALYTICS_DATASET}", ANALYTICS_DATASET)
    print(f"Running union job in {BQ_LOCATION}...")
    job_union = client_main.query(sql_union)
    job_union.result()
    print(f"Created/updated table {BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily")
    return 0


if __name__ == "__main__":
    sys.exit(main())
