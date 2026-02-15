"""Rules engine runner: delegates to rules.run_rules."""
from datetime import date
from typing import Optional

from sqlmodel import Session

from packages.rules_engine.src.rules import run_rules

__all__ = ["run_rules"]
