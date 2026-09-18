"""Harden FinancePeriod timeline integrity.

Revision ID: 1e10a020
Revises: 1e10a019
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a020"
down_revision = "1e10a019"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    invalid_range = bind.execute(
        sa.text(
            "SELECT id FROM finance_periods "
            "WHERE effective_to IS NOT NULL AND effective_to < effective_from "
            "LIMIT 1"
        )
    ).scalar()
    if invalid_range is not None:
        raise RuntimeError(
            "Cannot apply FinancePeriod integrity constraint: invalid date range exists."
        )

    overlapping = bind.execute(
        sa.text(
            "SELECT a.id FROM finance_periods a "
            "JOIN finance_periods b ON a.id < b.id "
            "AND a.effective_from <= COALESCE(b.effective_to, '9999-12-31') "
            "AND b.effective_from <= COALESCE(a.effective_to, '9999-12-31') "
            "LIMIT 1"
        )
    ).scalar()
    if overlapping is not None:
        raise RuntimeError(
            "Cannot apply FinancePeriod integrity constraint: overlapping periods exist."
        )

    with op.batch_alter_table("finance_periods") as batch_op:
        batch_op.create_check_constraint(
            "ck_finance_period_effective_range",
            "effective_to IS NULL OR effective_to >= effective_from",
        )


def downgrade():
    with op.batch_alter_table("finance_periods") as batch_op:
        batch_op.drop_constraint(
            "ck_finance_period_effective_range",
            type_="check",
        )
