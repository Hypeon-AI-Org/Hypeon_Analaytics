"""Opportunity agent: scale_opportunity and similar rules."""
from __future__ import annotations

from datetime import date
from typing import Optional

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.rules_engine import generate_insights


def run_opportunity_agent(
    client_id: int,
    as_of_date: date,
    rules_path: Optional[str] = None,
    write: bool = True,
) -> list:
    """Run opportunity rules (scale_opportunity); reuses generate_insights."""
    return generate_insights(client_id, as_of_date, rules_path=rules_path, write=write)
