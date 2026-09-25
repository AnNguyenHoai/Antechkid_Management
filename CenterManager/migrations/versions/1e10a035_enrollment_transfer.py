"""TUITION-13: add auditable Enrollment transfer ledger.

Revision ID: 1e10a035
Revises: 1e10a034

Transfer history links immutable source/target Enrollment contracts. Historical
payments and sessions are never rewritten and no transfer rows are inferred.
"""
from alembic import op
import sqlalchemy as sa


revision = "1e10a035"
down_revision = "1e10a034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrollment_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transferred_credit", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("source_balance_before", sa.Numeric(14, 4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("transferred_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("source_enrollment_id <> target_enrollment_id", name="ck_enrollment_transfer_distinct_contracts"),
        sa.CheckConstraint("transferred_credit >= 0", name="ck_enrollment_transfer_credit_nonnegative"),
        sa.UniqueConstraint("target_enrollment_id", name="uq_enrollment_transfer_target"),
    )
    op.create_index("ix_enrollment_transfers_source_enrollment_id", "enrollment_transfers", ["source_enrollment_id"], unique=False)
    op.create_index("ix_enrollment_transfers_target_enrollment_id", "enrollment_transfers", ["target_enrollment_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_enrollment_transfers_target_enrollment_id", table_name="enrollment_transfers")
    op.drop_index("ix_enrollment_transfers_source_enrollment_id", table_name="enrollment_transfers")
    op.drop_table("enrollment_transfers")
