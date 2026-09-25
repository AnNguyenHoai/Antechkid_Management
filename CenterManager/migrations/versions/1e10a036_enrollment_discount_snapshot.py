"""enrollment discount snapshot metadata

Revision ID: 1e10a036
Revises: 1e10a035
"""
from alembic import op
import sqlalchemy as sa


revision = "1e10a036"
down_revision = "1e10a035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("enrollments") as batch_op:
        batch_op.add_column(sa.Column("discount_type", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("discount_value", sa.Numeric(14, 4), nullable=True))
        batch_op.add_column(sa.Column("discount_source", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("discount_reason", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("discount_policy_version", sa.String(length=40), nullable=True))
        batch_op.create_check_constraint(
            "ck_enrollment_discount_type",
            "discount_type IS NULL OR discount_type IN ('FIXED', 'PERCENT')",
        )
        batch_op.create_check_constraint(
            "ck_enrollment_discount_value_nonnegative",
            "discount_value IS NULL OR discount_value >= 0",
        )
        batch_op.create_check_constraint(
            "ck_enrollment_discount_percent_range",
            "discount_type IS NULL OR discount_type != 'PERCENT' OR discount_value <= 100",
        )


def downgrade() -> None:
    with op.batch_alter_table("enrollments") as batch_op:
        batch_op.drop_constraint("ck_enrollment_discount_percent_range", type_="check")
        batch_op.drop_constraint("ck_enrollment_discount_value_nonnegative", type_="check")
        batch_op.drop_constraint("ck_enrollment_discount_type", type_="check")
        batch_op.drop_column("discount_policy_version")
        batch_op.drop_column("discount_reason")
        batch_op.drop_column("discount_source")
        batch_op.drop_column("discount_value")
        batch_op.drop_column("discount_type")
