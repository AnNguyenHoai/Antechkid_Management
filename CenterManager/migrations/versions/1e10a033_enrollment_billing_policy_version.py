"""TUITION-11: snapshot the tuition billing policy on Enrollment.

Revision ID: 1e10a033
Revises: 1e10a032

Existing rows are explicitly assigned the legacy session-only policy so enabling
attendance-aware billing cannot rewrite historical tuition meaning. New rows are
assigned the current policy by EnrollmentService.
"""
from alembic import op
import sqlalchemy as sa


revision = "1e10a033"
down_revision = "1e10a032"
branch_labels = None
depends_on = None


LEGACY_POLICY = "legacy_session_only_v1"


def upgrade() -> None:
    with op.batch_alter_table("enrollments") as batch_op:
        batch_op.add_column(
            sa.Column("billing_policy_version", sa.String(length=40), nullable=True)
        )

    op.execute(
        sa.text(
            "UPDATE enrollments SET billing_policy_version = :version "
            "WHERE billing_policy_version IS NULL"
        ).bindparams(version=LEGACY_POLICY)
    )

    with op.batch_alter_table("enrollments") as batch_op:
        batch_op.alter_column(
            "billing_policy_version",
            existing_type=sa.String(length=40),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("enrollments") as batch_op:
        batch_op.drop_column("billing_policy_version")
