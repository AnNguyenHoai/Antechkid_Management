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
    op.add_column("enrollments", sa.Column("discount_type", sa.String(length=20), nullable=True))
    op.add_column("enrollments", sa.Column("discount_value", sa.Numeric(14, 4), nullable=True))
    op.add_column("enrollments", sa.Column("discount_source", sa.String(length=40), nullable=True))
    op.add_column("enrollments", sa.Column("discount_reason", sa.String(length=255), nullable=True))
    op.add_column("enrollments", sa.Column("discount_policy_version", sa.String(length=40), nullable=True))
    op.create_check_constraint(
        "ck_enrollment_discount_type",
        "enrollments",
        "discount_type IS NULL OR discount_type IN ('FIXED', 'PERCENT')",
    )
    op.create_check_constraint(
        "ck_enrollment_discount_value_nonnegative",
        "enrollments",
        "discount_value IS NULL OR discount_value >= 0",
    )
    op.create_check_constraint(
        "ck_enrollment_discount_percent_range",
        "enrollments",
        "discount_type IS NULL OR discount_type != 'PERCENT' OR discount_value <= 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_enrollment_discount_percent_range", "enrollments", type_="check")
    op.drop_constraint("ck_enrollment_discount_value_nonnegative", "enrollments", type_="check")
    op.drop_constraint("ck_enrollment_discount_type", "enrollments", type_="check")
    op.drop_column("enrollments", "discount_policy_version")
    op.drop_column("enrollments", "discount_reason")
    op.drop_column("enrollments", "discount_source")
    op.drop_column("enrollments", "discount_value")
    op.drop_column("enrollments", "discount_type")
