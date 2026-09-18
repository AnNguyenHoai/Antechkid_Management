"""Harden FinancePeriod timeline integrity.

Revision ID: 1e10a020
Revises: 1e10a019
"""
from datetime import timedelta

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

    periods = bind.execute(
        sa.text(
            "SELECT id, effective_from, effective_to "
            "FROM finance_periods ORDER BY effective_from ASC"
        )
    ).mappings().all()

    # Normalize legacy overlap using the same latest-effective-from-wins timeline
    # semantics already used by Finance allocation. Adjacent ranges remain
    # inclusive and the latest configuration keeps its existing end date.
    for index, current in enumerate(periods[:-1]):
        next_period = periods[index + 1]
        max_end = next_period["effective_from"] - timedelta(days=1)
        if current["effective_to"] is None or current["effective_to"] > max_end:
            bind.execute(
                sa.text(
                    "UPDATE finance_periods "
                    "SET effective_to = :effective_to, status = 'INACTIVE' "
                    "WHERE id = :period_id"
                ),
                {"effective_to": max_end, "period_id": current["id"]},
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
