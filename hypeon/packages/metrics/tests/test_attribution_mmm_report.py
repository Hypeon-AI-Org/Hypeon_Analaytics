"""Tests for attribution vs MMM comparison report."""
from datetime import date

from sqlmodel import Session, create_engine, select
from sqlmodel.pool import StaticPool

from packages.shared.src import models  # noqa: F401
from packages.shared.src.models import AttributionEvent, MMMResults, RawMetaAds, RawGoogleAds
from sqlmodel import SQLModel
from packages.metrics.src.attribution_mmm_report import build_attribution_mmm_report


def test_build_report_empty():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        report = build_attribution_mmm_report(session, date(2025, 1, 1), date(2025, 1, 31))
    assert report["channels"] == []
    assert report["disagreement_score"] == 0.0
    assert report["instability_flagged"] is False


def test_build_report_with_attribution_and_mmm():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(AttributionEvent(
            order_id="o1", channel="meta", weight=0.6, allocated_revenue=60.0,
            event_date=date(2025, 1, 15), run_id="r1",
        ))
        session.add(AttributionEvent(
            order_id="o1", channel="google", weight=0.4, allocated_revenue=40.0,
            event_date=date(2025, 1, 15), run_id="r1",
        ))
        session.add(RawMetaAds(date=date(2025, 1, 15), campaign_id="c1", spend=100.0))
        session.add(RawGoogleAds(date=date(2025, 1, 15), campaign_id="g1", spend=50.0))
        session.add(MMMResults(run_id="r1", channel="meta", coefficient=1.0))
        session.add(MMMResults(run_id="r1", channel="google", coefficient=0.5))
        session.commit()
    with Session(engine) as session:
        report = build_attribution_mmm_report(session, date(2025, 1, 1), date(2025, 1, 31))
    assert "meta" in report["channels"] or "google" in report["channels"]
    assert 0 <= report["disagreement_score"] <= 2.0
    assert isinstance(report["instability_flagged"], bool)
