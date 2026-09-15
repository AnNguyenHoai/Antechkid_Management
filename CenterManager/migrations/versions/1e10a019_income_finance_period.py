"""Allocate Income records to canonical Finance periods.

Revision ID: 1e10a019
Revises: 1e10a018

EP-FIN-02. Legacy ``Income.payment_period`` remains compatible as display
metadata, while ``finance_period_start`` becomes the canonical period bucket
used by Income and Outstanding.
"""
from calendar import monthrange
from datetime import date

from alembic import op
import sqlalchemy as sa

revision = "1e10a019"
down_revision = "1e10a018"
branch_labels = None
depends_on = None


def _add_months(source_date: date, months: int) -> date:
    absolute = source_date.year * 12 + (source_date.month - 1) + months
    year, month_index = divmod(absolute, 12)
    month = month_index + 1
    day = min(source_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _period_start(anchor_date: date, target_date: date, duration_months: int) -> date:
    months = (
        (target_date.year - anchor_date.year) * 12
        + target_date.month
        - anchor_date.month
    )
    candidate = _add_months(anchor_date, months)
    if candidate > target_date:
        months -= 1
    bucket = months // duration_months
    return _add_months(anchor_date, bucket * duration_months)


def upgrade():
    op.add_column("incomes", sa.Column("finance_period_start", sa.Date(), nullable=True))
    op.create_index(
        "ix_incomes_finance_period_start",
        "incomes",
        ["finance_period_start"],
        unique=False,
    )

    bind = op.get_bind()
    periods = bind.execute(
        sa.text(
            "SELECT effective_from, effective_to, duration_months "
            "FROM finance_periods ORDER BY effective_from"
        )
    ).mappings().all()
    if not periods:
        return

    incomes = bind.execute(
        sa.text("SELECT id, payment_date FROM incomes WHERE finance_period_start IS NULL")
    ).mappings().all()

    for income in incomes:
        payment_date = income["payment_date"]
        if payment_date is None:
            continue
        config = None
        for candidate in periods:
            if candidate["effective_from"] <= payment_date and (
                candidate["effective_to"] is None or candidate["effective_to"] >= payment_date
            ):
                config = candidate
        if config is None:
            continue
        start = _period_start(
            config["effective_from"],
            payment_date,
            config["duration_months"],
        )
        bind.execute(
            sa.text(
                "UPDATE incomes SET finance_period_start = :period_start WHERE id = :income_id"
            ),
            {"period_start": start, "income_id": income["id"]},
        )


def downgrade():
    op.drop_index("ix_incomes_finance_period_start", table_name="incomes")
    op.drop_column("incomes", "finance_period_start")
