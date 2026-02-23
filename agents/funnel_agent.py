"""Funnel agent: funnel_leak and conversion-focused rules."""
from __future__ import annotations

from datetime import date
from typing import Optional

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.rules_engine import generate_insights


def run_funnel_agent(
    client_id: int,
    as_of_date: date,
    rules_path: Optional[str] = None,
    write: bool = True,
) -> list:
    """Run funnel rules (e.g. funnel_leak); reuses generate_insights."""
    return generate_insights(client_id, as_of_date, rules_path=rules_path, write=write)
