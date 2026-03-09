"""Backend config from environment."""
from __future__ import annotations

import os
from typing import List


def get_bq_project() -> str:
    """GCP project from env only; no default (client privacy)."""
    return os.environ.get("BQ_PROJECT") or ""


def get_source_bq_project() -> str:
    """GCP project for raw data; from env only (client privacy)."""
    return os.environ.get("BQ_SOURCE_PROJECT") or get_bq_project()


def get_analytics_dataset() -> str:
    return os.environ.get("ANALYTICS_DATASET") or ""


def get_marts_dataset() -> str:
    """From env only; no default (client privacy). Copilot uses Firestore org config."""
    return os.environ.get("MARTS_DATASET") or ""


def get_ads_dataset() -> str:
    """From env only; no default (client privacy)."""
    return os.environ.get("ADS_DATASET") or ""


def get_ga4_dataset() -> str:
    """From env only; no default (client privacy)."""
    return os.environ.get("GA4_DATASET") or ""


def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "")


def get_api_key() -> str | None:
    v = os.environ.get("API_KEY")
    if not v or not isinstance(v, str):
        return None
    v = v.strip().replace("\r", "")
    return v or None


def get_cors_origins() -> List[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [x.strip() for x in raw.split(",") if x.strip()]
