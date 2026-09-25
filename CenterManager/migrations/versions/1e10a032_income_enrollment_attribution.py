"""TUITION-07: link tuition Income to Enrollment.

Revision ID: 1e10a032
Revises: 1e10a031

Historical Income rows intentionally remain NULL. There is no inferred backfill:
legacy Tuition attribution requires explicit reconciliation because Student + Class
can have multiple Enrollment contracts.
"""
from alembic import op
import sqlalchemy as sa


revision = "1e10a032"
down_revision = "1e10a031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incomes") as batch_op:
        batch_op.add_column(sa.Column("enrollment_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_incomes_enrollment_id_enrollments",
            "enrollments",
            ["enrollment_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_incomes_enrollment_id",
            ["enrollment_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("incomes") as batch_op:
        batch_op.drop_index("ix_incomes_enrollment_id")
        batch_op.drop_constraint(
            "fk_incomes_enrollment_id_enrollments",
            type_="foreignkey",
        )
        batch_op.drop_column("enrollment_id")
