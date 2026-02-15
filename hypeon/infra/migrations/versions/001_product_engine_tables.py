"""Product-engine tables: raw, attribution, metrics, mmm, decision_store, store_config.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_meta_ads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("campaign_name", sa.String(), nullable=True),
        sa.Column("spend", sa.Float(), nullable=False, server_default="0"),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "raw_google_ads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("campaign_name", sa.String(), nullable=True),
        sa.Column("spend", sa.Float(), nullable=False, server_default="0"),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "raw_shopify_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("revenue", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_new_customer", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "attribution_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=True),
        sa.Column("cost_center", sa.String(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("allocated_revenue", sa.Float(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
    )
    op.create_table(
        "unified_daily_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("spend", sa.Float(), nullable=False, server_default="0"),
        sa.Column("attributed_revenue", sa.Float(), nullable=False, server_default="0"),
        sa.Column("roas", sa.Float(), nullable=True),
        sa.Column("mer", sa.Float(), nullable=True),
        sa.Column("cac", sa.Float(), nullable=True),
        sa.Column("revenue_new", sa.Float(), nullable=True),
        sa.Column("revenue_returning", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "mmm_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("coefficient", sa.Float(), nullable=False),
        sa.Column("saturation_half_life", sa.Float(), nullable=True),
        sa.Column("saturation_alpha", sa.Float(), nullable=True),
        sa.Column("goodness_of_fit_r2", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
    )
    op.create_table(
        "decision_store",
        sa.Column("decision_id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("decision_type", sa.String(), nullable=False),
        sa.Column("reason_code", sa.String(), nullable=False),
        sa.Column("explanation_text", sa.String(), nullable=True),
        sa.Column("projected_impact", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
    )
    op.create_table(
        "store_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value_json", sa.String(), nullable=True),
        sa.Column("value_float", sa.Float(), nullable=True),
        sa.Column("value_int", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_attribution_events_run_id", "attribution_events", ["run_id"])
    op.create_index("ix_unified_daily_metrics_date_channel", "unified_daily_metrics", ["date", "channel"])
    op.create_index("ix_mmm_results_run_id", "mmm_results", ["run_id"])
    op.create_index("ix_decision_store_status", "decision_store", ["status"])


def downgrade() -> None:
    op.drop_index("ix_decision_store_status", "decision_store")
    op.drop_index("ix_mmm_results_run_id", "mmm_results")
    op.drop_index("ix_unified_daily_metrics_date_channel", "unified_daily_metrics")
    op.drop_index("ix_attribution_events_run_id", "attribution_events")
    op.drop_table("store_config")
    op.drop_table("decision_store")
    op.drop_table("mmm_results")
    op.drop_table("unified_daily_metrics")
    op.drop_table("attribution_events")
    op.drop_table("raw_shopify_orders")
    op.drop_table("raw_google_ads")
    op.drop_table("raw_meta_ads")
