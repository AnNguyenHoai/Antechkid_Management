"""Add legacy Enrollment reconciliation lineage.

Revision ID: 1e10a040
Revises: 1e10a039
Create Date: 2026-10-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "1e10a040"
down_revision = "1e10a039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("enrollments") as batch:
        batch.add_column(
            sa.Column("reconciled_into_enrollment_id", sa.Integer(), nullable=True)
        )
        batch.add_column(sa.Column("reconciled_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("reconciled_by", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("reconcile_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("reconciliation_reviewed_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("reconciliation_reviewed_by", sa.String(length=100), nullable=True)
        )
        batch.add_column(sa.Column("reconciliation_review_reason", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_enrollments_reconciled_into",
            "enrollments",
            ["reconciled_into_enrollment_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_enrollments_reconciled_into_enrollment_id",
            ["reconciled_into_enrollment_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("enrollments") as batch:
        batch.drop_index("ix_enrollments_reconciled_into_enrollment_id")
        batch.drop_constraint("fk_enrollments_reconciled_into", type_="foreignkey")
        batch.drop_column("reconciliation_review_reason")
        batch.drop_column("reconciliation_reviewed_by")
        batch.drop_column("reconciliation_reviewed_at")
        batch.drop_column("reconcile_reason")
        batch.drop_column("reconciled_by")
        batch.drop_column("reconciled_at")
        batch.drop_column("reconciled_into_enrollment_id")
