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
    finance_periods = sa.table(
        "finance_periods",
        sa.column("id", sa.Integer()),
        sa.column("effective_from", sa.Date()),
        sa.column("effective_to", sa.Date()),
        sa.column("status", sa.String(20)),
    )

    invalid_range = bind.execute(
        sa.select(finance_periods.c.id)
        .where(
            finance_periods.c.effective_to.is_not(None),
            finance_periods.c.effective_to < finance_periods.c.effective_from,
        )
        .limit(1)
    ).scalar()
    if invalid_range is not None:
        raise RuntimeError(
            "Cannot apply FinancePeriod integrity constraint: invalid date range exists."
        )

    periods = bind.execute(
        sa.select(
            finance_periods.c.id,
            finance_periods.c.effective_from,
            finance_periods.c.effective_to,
        ).order_by(finance_periods.c.effective_from.asc())
    ).mappings().all()

    # Normalize legacy overlap using the same latest-effective-from-wins timeline
    # semantics already used by Finance allocation. Adjacent ranges remain
    # inclusive and the latest configuration keeps its existing end date.
    for index, current in enumerate(periods[:-1]):
        next_period = periods[index + 1]
        max_end = next_period["effective_from"] - timedelta(days=1)
        if current["effective_to"] is None or current["effective_to"] > max_end:
            bind.execute(
                sa.update(finance_periods)
                .where(finance_periods.c.id == current["id"])
                .values(effective_to=max_end, status="INACTIVE")
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
