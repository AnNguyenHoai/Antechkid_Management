"""Add canonical finance period identity to incomes.

Revision ID: 1e10a027
Revises: 1e10a026
Create Date: 2026-09-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "1e10a027"
down_revision = "1e10a026"
branch_labels = None
depends_on = None

_FK_NAME = "fk_incomes_finance_period_id_finance_periods"
_INDEX_NAME = "ix_incomes_finance_period_id"


def upgrade() -> None:
    with op.batch_alter_table("incomes") as batch_op:
        batch_op.add_column(sa.Column("finance_period_id", sa.Integer(), nullable=True))
        batch_op.create_index(_INDEX_NAME, ["finance_period_id"], unique=False)
        batch_op.create_foreign_key(
            _FK_NAME,
            "finance_periods",
            ["finance_period_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("incomes") as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
        batch_op.drop_index(_INDEX_NAME)
        batch_op.drop_column("finance_period_id")
