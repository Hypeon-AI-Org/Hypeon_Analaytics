"""Add copilot_sessions and copilot_messages for chat history.

Revision ID: 004
Revises: 003
Create Date: 2025-02-14 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "copilot_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("copilot_sessions.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_copilot_messages_session_id", "copilot_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_copilot_messages_session_id", "copilot_messages")
    op.drop_table("copilot_messages")
    op.drop_table("copilot_sessions")
