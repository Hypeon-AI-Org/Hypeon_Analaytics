"""Load YAML config by environment (ENV=dev|staging|prod)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_env = os.environ.get("ENV", "dev")
_config: dict[str, Any] | None = None


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_config() -> dict[str, Any]:
    global _config
    if _config is not None:
        return _config
    path = CONFIG_DIR / f"{_env}.yaml"
    if path.exists():
        _config = _load_yaml(path)
    else:
        _config = {}
    # Override from env
    for key in ["bq_project", "analytics_dataset", "log_level", "top_insights_per_client"]:
        env_key = key.upper()
        val = os.environ.get(env_key)
        if val is not None:
            if key == "top_insights_per_client":
                try:
                    _config[key] = int(val)
                except ValueError:
                    pass
            else:
                _config[key] = val
    return _config


def get(key: str, default: Any = None) -> Any:
    return get_config().get(key, default)
