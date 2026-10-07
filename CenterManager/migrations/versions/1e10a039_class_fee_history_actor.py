"""Add editor attribution to Class fee history.

Revision ID: 1e10a039
Revises: 1e10a038
Create Date: 2026-10-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "1e10a039"
down_revision = "1e10a038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "class_fee_history",
        sa.Column("changed_by", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("class_fee_history", "changed_by")
