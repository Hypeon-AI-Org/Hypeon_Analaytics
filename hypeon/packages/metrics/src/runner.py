"""Metrics runner: delegates to aggregator.run_metrics."""
from datetime import date
from typing import Optional

from sqlmodel import Session

from packages.metrics.src.aggregator import run_metrics

# Re-export
__all__ = ["run_metrics"]
