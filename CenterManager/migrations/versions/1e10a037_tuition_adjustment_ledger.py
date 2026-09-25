"""tuition adjustment ledger

Revision ID: 1e10a037
Revises: 1e10a036
"""
from alembic import op
import sqlalchemy as sa


revision = "1e10a037"
down_revision = "1e10a036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tuition_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), nullable=False),
        sa.Column("origin_income_id", sa.Integer(), nullable=True),
        sa.Column("origin_adjustment_id", sa.Integer(), nullable=True),
        sa.Column("linked_income_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("adjustment_date", sa.Date(), nullable=False),
        sa.Column("wallet", sa.String(length=20), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["origin_income_id"], ["incomes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["origin_adjustment_id"], ["tuition_adjustments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["linked_income_id"], ["incomes.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("kind IN ('REFUND', 'CREDIT_ADJUSTMENT')", name="ck_tuition_adjustment_kind"),
        sa.CheckConstraint("amount > 0", name="ck_tuition_adjustment_amount_positive"),
        sa.CheckConstraint(
            "(kind = 'REFUND' AND linked_income_id IS NOT NULL AND wallet IS NOT NULL AND origin_adjustment_id IS NULL) "
            "OR (kind = 'CREDIT_ADJUSTMENT' AND linked_income_id IS NULL AND wallet IS NULL AND origin_income_id IS NULL)",
            name="ck_tuition_adjustment_shape",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_tuition_adjustment_idempotency_key"),
        sa.UniqueConstraint("linked_income_id", name="uq_tuition_adjustment_linked_income"),
    )
    op.create_index("ix_tuition_adjustments_enrollment_id", "tuition_adjustments", ["enrollment_id"])
    op.create_index("ix_tuition_adjustments_origin_income_id", "tuition_adjustments", ["origin_income_id"])
    op.create_index("ix_tuition_adjustments_origin_adjustment_id", "tuition_adjustments", ["origin_adjustment_id"])
    op.create_index("ix_tuition_adjustments_linked_income_id", "tuition_adjustments", ["linked_income_id"])
    op.create_index("ix_tuition_adjustments_kind", "tuition_adjustments", ["kind"])
    op.create_index("ix_tuition_adjustments_adjustment_date", "tuition_adjustments", ["adjustment_date"])


def downgrade() -> None:
    op.drop_index("ix_tuition_adjustments_adjustment_date", table_name="tuition_adjustments")
    op.drop_index("ix_tuition_adjustments_kind", table_name="tuition_adjustments")
    op.drop_index("ix_tuition_adjustments_linked_income_id", table_name="tuition_adjustments")
    op.drop_index("ix_tuition_adjustments_origin_adjustment_id", table_name="tuition_adjustments")
    op.drop_index("ix_tuition_adjustments_origin_income_id", table_name="tuition_adjustments")
    op.drop_index("ix_tuition_adjustments_enrollment_id", table_name="tuition_adjustments")
    op.drop_table("tuition_adjustments")
