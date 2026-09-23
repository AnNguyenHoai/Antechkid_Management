"""FW2-02 add canonical FinancePeriod assignment to Expense.

Revision ID: 1e10a026
Revises: 1e10a025
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a026"
down_revision = "1e10a025"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable by design: legacy rows are reconciled explicitly in FW2-09. New
    # realized postings are required by the service to have a deterministic FK.
    with op.batch_alter_table("expenses") as batch:
        batch.add_column(sa.Column("finance_period_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_expenses_finance_period",
            "finance_periods",
            ["finance_period_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_expenses_finance_period_id", ["finance_period_id"], unique=False)


def downgrade():
    with op.batch_alter_table("expenses") as batch:
        batch.drop_index("ix_expenses_finance_period_id")
        batch.drop_constraint("fk_expenses_finance_period", type_="foreignkey")
        batch.drop_column("finance_period_id")
