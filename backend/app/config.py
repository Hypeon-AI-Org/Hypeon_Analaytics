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


def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "")


def get_api_key() -> str | None:
    return os.environ.get("API_KEY")


def get_cors_origins() -> List[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [x.strip() for x in raw.split(",") if x.strip()]
