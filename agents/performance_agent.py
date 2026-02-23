"""Performance agent: evaluates performance rules and writes insights to BigQuery."""
from __future__ import annotations

from datetime import date
from typing import Optional

# Assume agents run from repo root or backend is on path
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.rules_engine import generate_insights


def run_performance_agent(
    client_id: int,
    as_of_date: date,
    rules_path: Optional[str] = None,
    write: bool = True,
) -> list:
    """Run performance rules (waste_zero_revenue, roas_decline, scale_opportunity) and return insights."""
    return generate_insights(client_id, as_of_date, rules_path=rules_path, write=write)
