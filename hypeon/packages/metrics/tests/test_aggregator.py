"""Tests for metrics aggregation."""
from datetime import date

from sqlmodel import Session, create_engine, select
from sqlmodel.pool import StaticPool

from packages.shared.src import models  # noqa: F401
from packages.shared.src.models import (
    RawMetaAds,
    RawGoogleAds,
    RawShopifyOrders,
    AttributionEvent,
    UnifiedDailyMetrics,
)
from sqlmodel import SQLModel
from packages.metrics.src.aggregator import compute_unified_metrics, run_metrics


def test_compute_unified_metrics_empty():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        out = compute_unified_metrics(session, date(2025, 1, 1), date(2025, 1, 31))
        assert out == []


def test_compute_unified_metrics_with_spend_and_attribution():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(RawMetaAds(date=date(2025, 1, 1), campaign_id="c1", spend=100.0))
        session.add(AttributionEvent(
            order_id="o1", channel="meta", weight=1.0, allocated_revenue=200.0,
            event_date=date(2025, 1, 1), run_id="r1",
        ))
        session.commit()
    with Session(engine) as session:
        out = compute_unified_metrics(session, date(2025, 1, 1), date(2025, 1, 31))
        assert len(out) >= 1
        row = next(r for r in out if r.channel == "meta")
        assert row.spend == 100.0
        assert row.attributed_revenue == 200.0
        assert row.roas == 2.0
