"""Add raw_shopify_transactions, extend raw_shopify_orders, add ingest_audit.

Revision ID: 003
Revises: 002
Create Date: 2025-02-01 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend raw_shopify_orders (all new columns nullable for backward compatibility)
    op.add_column("raw_shopify_orders", sa.Column("name", sa.String(), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("closed_at", sa.DateTime(), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("financial_status", sa.String(), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("fulfillment_status", sa.String(), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("total_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("subtotal_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("total_tax", sa.Numeric(12, 2), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("source_name", sa.String(), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("line_items_json", sa.JSON(), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.add_column("raw_shopify_orders", sa.Column("is_test", sa.Boolean(), nullable=True, server_default="false"))
    op.add_column("raw_shopify_orders", sa.Column("net_revenue", sa.Numeric(12, 2), nullable=True))
    # created_at already exists; ensure it exists (001 has created_at)

    # raw_shopify_transactions
    op.create_table(
        "raw_shopify_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("raw_shopify_orders.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("gateway", sa.String(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("source_name", sa.String(), nullable=True),
    )
    op.create_index("ix_raw_shopify_transactions_order_id", "raw_shopify_transactions", ["order_id"])

    # ingest_audit
    op.create_table(
        "ingest_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("computed_net_revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("diff", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("note", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ingest_audit")
    op.drop_index("ix_raw_shopify_transactions_order_id", "raw_shopify_transactions")
    op.drop_table("raw_shopify_transactions")
    for col in [
        "net_revenue", "is_test", "customer_id", "line_items_json", "source_name",
        "currency", "total_tax", "subtotal_price", "total_price", "fulfillment_status",
        "financial_status", "cancelled_at", "closed_at", "name",
    ]:
        op.drop_column("raw_shopify_orders", col)
