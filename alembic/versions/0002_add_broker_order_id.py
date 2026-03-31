"""add broker_order_id to trades

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trades",
        sa.Column("broker_order_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trades", "broker_order_id")
