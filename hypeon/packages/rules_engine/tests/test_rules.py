"""Tests for rules evaluation."""
from datetime import date

from sqlmodel import Session, create_engine, select
from sqlmodel.pool import StaticPool

from packages.shared.src import models  # noqa: F401
from packages.shared.src.models import StoreConfig, UnifiedDailyMetrics, DecisionStore
from sqlmodel import SQLModel
from packages.rules_engine.src.rules import evaluate_rules


def test_evaluate_rules_scale_up():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(StoreConfig(key="roas_scale_up_threshold", value_float=2.0))
        session.add(UnifiedDailyMetrics(
            date=date(2025, 1, 15), channel="meta", spend=100.0, attributed_revenue=300.0, roas=3.0
        ))
        session.commit()
    with Session(engine) as session:
        decisions = evaluate_rules(session, date(2025, 1, 1), date(2025, 1, 31))
        assert len(decisions) >= 1
        scale_ups = [d for d in decisions if d.decision_type == "scale_up"]
        assert any(d.entity_id == "meta" for d in scale_ups)
