"""Backend config from environment."""
from __future__ import annotations

import os
from typing import List


def get_bq_project() -> str:
    """GCP project for application DB (analytics_insights, marketing_performance_daily, marts, etc.)."""
    return os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")


def get_source_bq_project() -> str:
    """GCP project for raw input data (Ads, GA4). Defaults to BQ_PROJECT if unset (single-project setup)."""
    return os.environ.get("BQ_SOURCE_PROJECT") or get_bq_project()


def get_analytics_dataset() -> str:
    return os.environ.get("ANALYTICS_DATASET", "analytics")


def get_marts_dataset() -> str:
    """Dataset for marts layer (hypeon_marts). Copilot queries this."""
    return os.environ.get("MARTS_DATASET", "hypeon_marts")


def get_ads_dataset() -> str:
    """From .env ADS_DATASET (e.g. 146568). Never delete this dataset."""
    return os.environ.get("ADS_DATASET", "146568")


def get_ga4_dataset() -> str:
    """From .env GA4_DATASET (e.g. analytics_444259275). Never delete this dataset."""
    return os.environ.get("GA4_DATASET", "analytics_444259275")


def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "")


def get_api_key() -> str | None:
    return os.environ.get("API_KEY")


def get_cors_origins() -> List[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [x.strip() for x in raw.split(",") if x.strip()]
