"""Repair post-PR-J schema drift without rewriting production tables.

Revision ID: 1e10a041
Revises: 1e10a040
Create Date: 2026-10-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "1e10a041"
down_revision = "1e10a040"
branch_labels = None
depends_on = None


_ENROLLMENT_COLUMNS = (
    ("reconciled_into_enrollment_id", sa.Integer()),
    ("reconciled_at", sa.DateTime()),
    ("reconciled_by", sa.String(length=100)),
    ("reconcile_reason", sa.Text()),
    ("reconciliation_reviewed_at", sa.DateTime()),
    ("reconciliation_reviewed_by", sa.String(length=100)),
    ("reconciliation_review_reason", sa.Text()),
)


def _column_names(bind, table_name: str) -> set[str]:
    return {
        column["name"]
        for column in inspect(bind).get_columns(table_name)
    }


def _index_names(bind, table_name: str) -> set[str]:
    return {
        index["name"]
        for index in inspect(bind).get_indexes(table_name)
        if index.get("name")
    }


def upgrade() -> None:
    """Repair databases whose Alembic revision was stamped ahead of real schema.

    Earlier production attempts could reach revision 1e10a040 while runtime
    schema changes were incomplete.  This revision is intentionally idempotent:
    it inspects the authoritative DB and adds only missing nullable columns and
    the reconciliation lookup index.
    """
    bind = op.get_bind()

    enrollment_columns = _column_names(bind, "enrollments")
    for name, column_type in _ENROLLMENT_COLUMNS:
        if name not in enrollment_columns:
            op.add_column(
                "enrollments",
                sa.Column(name, column_type, nullable=True),
            )

    class_fee_columns = _column_names(bind, "class_fee_history")
    if "changed_by" not in class_fee_columns:
        op.add_column(
            "class_fee_history",
            sa.Column("changed_by", sa.String(length=100), nullable=True),
        )

    enrollment_indexes = _index_names(bind, "enrollments")
    index_name = "ix_enrollments_reconciled_into_enrollment_id"
    if index_name not in enrollment_indexes:
        op.create_index(
            index_name,
            "enrollments",
            ["reconciled_into_enrollment_id"],
            unique=False,
        )


def downgrade() -> None:
    # The repository already treats the historical weekly migration chain as
    # globally irreversible.  Keep this repair revision schema-neutral on the
    # way down so that the canonical irreversible guard remains authoritative.
    pass
