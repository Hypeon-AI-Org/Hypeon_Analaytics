"""Tests for order reconciliation: net_revenue = sales - refunds, audit rows."""
from datetime import date
from pathlib import Path

from sqlmodel import Session, create_engine, select
from sqlmodel.pool import StaticPool

from packages.shared.src import models  # noqa: F401
from packages.shared.src.ingest import load_shopify_orders, load_shopify_transactions, reconcile_orders
from packages.shared.src.models import IngestAudit, RawShopifyOrders, RawShopifyTransactions
from sqlmodel import SQLModel


def test_reconcile_orders_sale_minus_refund_stored():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            RawShopifyOrders(
                order_id="o1",
                order_date=date(2025, 1, 1),
                revenue=200.0,
                total_price=200.0,
                net_revenue=200.0,
            )
        )
        session.commit()
        order = session.exec(select(RawShopifyOrders).where(RawShopifyOrders.order_id == "o1")).first()
        assert order and order.id is not None
        session.add(RawShopifyTransactions(order_id=order.id, kind="sale", status="success", amount=200.0))
        session.add(RawShopifyTransactions(order_id=order.id, kind="refund", status="success", amount=-50.0))
        session.commit()
    with Session(engine) as session:
        n = reconcile_orders(session)
        assert n == 1
        order = session.exec(select(RawShopifyOrders).where(RawShopifyOrders.order_id == "o1")).first()
        assert order is not None
        assert order.net_revenue == 150.0
        audit = session.exec(select(IngestAudit).where(IngestAudit.order_id == "o1")).first()
        assert audit is not None
        assert audit.computed_net_revenue == 150.0
        assert audit.note in ("refunds", "tx_reconcile")


def test_reconcile_cancelled_order_zero_net():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    from datetime import datetime
    with Session(engine) as session:
        session.add(
            RawShopifyOrders(
                order_id="o2",
                order_date=date(2025, 1, 1),
                revenue=100.0,
                cancelled_at=datetime(2025, 1, 2),
            )
        )
        session.commit()
        order = session.exec(select(RawShopifyOrders).where(RawShopifyOrders.order_id == "o2")).first()
        session.add(RawShopifyTransactions(order_id=order.id, kind="sale", status="success", amount=100.0))
        session.commit()
    with Session(engine) as session:
        reconcile_orders(session)
        order = session.exec(select(RawShopifyOrders).where(RawShopifyOrders.order_id == "o2")).first()
        assert order.net_revenue == 0.0


def test_reconcile_fixtures_integration():
    """Run load orders + transactions from fixtures then reconcile; assert one order has net = sale - refund."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    fixtures = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw" / "fixtures"
    if not (fixtures / "shopify_orders.csv").exists():
        return
    with Session(engine) as session:
        load_shopify_orders(session, csv_path=fixtures / "shopify_orders.csv")
        load_shopify_transactions(session, csv_path=fixtures / "shopify_transactions.csv")
        reconcile_orders(session)
    with Session(engine) as session:
        order1003 = session.exec(select(RawShopifyOrders).where(RawShopifyOrders.order_id == "1003")).first()
        if order1003:
            assert order1003.net_revenue == 150.0
        order1005 = session.exec(select(RawShopifyOrders).where(RawShopifyOrders.order_id == "1005")).first()
        if order1005:
            assert order1005.net_revenue == 0.0
