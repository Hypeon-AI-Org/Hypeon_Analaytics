"""Add unique constraints for raw table upserts.

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:01:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_raw_meta_ads_date_campaign",
        "raw_meta_ads",
        ["date", "campaign_id"],
    )
    op.create_unique_constraint(
        "uq_raw_google_ads_date_campaign",
        "raw_google_ads",
        ["date", "campaign_id"],
    )
    op.create_unique_constraint("uq_raw_shopify_orders_order_id", "raw_shopify_orders", ["order_id"])


def downgrade() -> None:
    op.drop_constraint("uq_raw_meta_ads_date_campaign", "raw_meta_ads", type_="unique")
    op.drop_constraint("uq_raw_google_ads_date_campaign", "raw_google_ads", type_="unique")
    op.drop_constraint("uq_raw_shopify_orders_order_id", "raw_shopify_orders", type_="unique")
