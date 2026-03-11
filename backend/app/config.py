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


def _load_api_key_from_env_file() -> str | None:
    """Load API_KEY from .env file (used when process env not inherited, e.g. uvicorn --reload worker)."""
    from pathlib import Path
    cwd = Path.cwd()
    candidates = [
        Path(__file__).resolve().parents[2] / ".env",  # backend/app/config.py -> repo root
        cwd.parent / ".env" if cwd.name == "backend" else None,
        cwd / ".env",
        cwd.parent / ".env",
        cwd.parent / "backend" / ".env",
    ]
    for _env in candidates:
        if _env is None or not _env.exists():
            continue
        try:
            raw = _env.read_text(encoding="utf-8")
            for line in raw.splitlines():
                line = line.strip().replace("\r", "")
                if line.startswith("API_KEY=") and "=" in line:
                    v = line.split("=", 1)[1].strip().strip("'\"").replace("\r", "")
                    if v:
                        return v
        except Exception:
            continue
    return None


def get_api_key() -> str | None:
    v = os.environ.get("API_KEY")
    if not v or not isinstance(v, str):
        v = _load_api_key_from_env_file()
        if v:
            os.environ["API_KEY"] = v
            return v
        return None
    v = v.strip().replace("\r", "")
    return v or None


def get_cors_origins() -> List[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [x.strip() for x in raw.split(",") if x.strip()]
