"""Add FinancePeriod financial settlement snapshots.

Revision ID: 1e10a021
Revises: 1e10a020
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a021"
down_revision = "1e10a020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "financial_settlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finance_period_start", sa.Date(), nullable=False),
        sa.Column("finance_period_end", sa.Date(), nullable=False),
        sa.Column("opening_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("opening_bank", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("income_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("income_bank", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expense_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expense_bank", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expected_closing_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expected_closing_bank", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("actual_closing_cash", sa.Numeric(14, 2), nullable=True),
        sa.Column("actual_closing_bank", sa.Numeric(14, 2), nullable=True),
        sa.Column("difference_cash", sa.Numeric(14, 2), nullable=True),
        sa.Column("difference_bank", sa.Numeric(14, 2), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("confirmed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("finance_period_start", name="uq_financial_settlement_period_start"),
        sa.CheckConstraint(
            "finance_period_end >= finance_period_start",
            name="ck_financial_settlement_period_range",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'CONFIRMED')",
            name="ck_financial_settlement_status",
        ),
    )


def downgrade():
    op.drop_table("financial_settlements")
