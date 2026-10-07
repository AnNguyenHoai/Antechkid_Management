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
    # SQLite/SQLCipher production safety:
    # these lineage fields are all nullable and require no table rewrite.
    # Using batch_alter_table here would rebuild the entire enrollments table,
    # and the self-referencing FK previously made that rebuild vulnerable to
    # long-running/blocked DDL on the authoritative runtime database.
    op.add_column(
        "enrollments",
        sa.Column("reconciled_into_enrollment_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("reconciled_by", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("reconcile_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("reconciliation_reviewed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("reconciliation_reviewed_by", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("reconciliation_review_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_enrollments_reconciled_into_enrollment_id",
        "enrollments",
        ["reconciled_into_enrollment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_enrollments_reconciled_into_enrollment_id",
        table_name="enrollments",
    )
    with op.batch_alter_table("enrollments") as batch:
        batch.drop_column("reconciliation_review_reason")
        batch.drop_column("reconciliation_reviewed_by")
        batch.drop_column("reconciliation_reviewed_at")
        batch.drop_column("reconcile_reason")
        batch.drop_column("reconciled_by")
        batch.drop_column("reconciled_at")
        batch.drop_column("reconciled_into_enrollment_id")
