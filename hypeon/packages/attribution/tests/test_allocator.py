"""Tests for fractional attribution allocator."""
import pandas as pd

from packages.attribution.src.allocator import fractional_allocate


def test_fractional_by_spend_share():
    orders = pd.DataFrame({
        "order_id": ["o1", "o2"],
        "order_date": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-01")],
        "revenue": [100.0, 50.0],
    })
    daily = pd.DataFrame({
        "date": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-01")],
        "channel": ["meta", "google"],
        "spend": [60.0, 40.0],
    })
    out = fractional_allocate(orders, daily)
    assert len(out) == 4
    order_ids = {r[0] for r in out}
    assert order_ids == {"o1", "o2"}
    for r in out:
        order_id, _, channel, weight, alloc = r
        assert weight >= 0 and weight <= 1
        assert alloc >= 0
    total_o1 = sum(alloc for oid, *_ in [r for r in out if r[0] == "o1"] for r in [out] for alloc in [r[4]])
    total_o1 = sum(r[4] for r in out if r[0] == "o1")
    assert abs(total_o1 - 100.0) < 1e-6
    total_o2 = sum(r[4] for r in out if r[0] == "o2")
    assert abs(total_o2 - 50.0) < 1e-6


def test_fractional_custom_weights():
    orders = pd.DataFrame({
        "order_id": ["o1"],
        "order_date": [pd.Timestamp("2025-01-01")],
        "revenue": [100.0],
    })
    daily = pd.DataFrame({"date": [], "channel": [], "spend": []})
    out = fractional_allocate(orders, daily, channel_weights={"meta": 0.6, "google": 0.4})
    assert len(out) == 2
    meta_alloc = next(r[4] for r in out if r[2] == "meta")
    assert abs(meta_alloc - 60.0) < 1e-6
    google_alloc = next(r[4] for r in out if r[2] == "google")
    assert abs(google_alloc - 40.0) < 1e-6
