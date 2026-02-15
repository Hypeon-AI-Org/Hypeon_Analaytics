"""Tests for CSV ingest."""
import tempfile
from pathlib import Path

import pandas as pd
from sqlmodel import Session, create_engine, select
from sqlmodel.pool import StaticPool

from packages.shared.src import models  # noqa: F401
from packages.shared.src.ingest import load_meta_ads, run_ingest
from packages.shared.src.models import RawMetaAds
from sqlmodel import SQLModel


def test_load_meta_ads_creates_rows():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        path = Path(f.name)
    try:
        pd.DataFrame({
            "date": ["2025-01-01", "2025-01-02"],
            "campaign_id": ["c1", "c1"],
            "spend": [10.0, 20.0],
        }).to_csv(path, index=False)
        with Session(engine) as session:
            n = load_meta_ads(session, csv_path=path)
            assert n == 2
            rows = list(session.exec(select(RawMetaAds)).all())
            assert len(rows) == 2
    finally:
        path.unlink(missing_ok=True)


def test_run_ingest_empty_dir_returns_zero_counts():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with tempfile.TemporaryDirectory() as d:
        with Session(engine) as session:
            counts = run_ingest(session, data_dir=Path(d))
            assert counts["meta_ads"] == 0
            assert counts["google_ads"] == 0
            assert counts["shopify_orders"] == 0
            assert counts.get("shopify_transactions", 0) == 0
            assert counts.get("reconciled_orders", 0) == 0
