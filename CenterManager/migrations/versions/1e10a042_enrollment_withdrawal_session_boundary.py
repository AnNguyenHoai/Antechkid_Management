"""Add exact Enrollment withdrawal session boundary.

Revision ID: 1e10a042
Revises: 1e10a041
Create Date: 2026-10-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "1e10a042"
down_revision = "1e10a041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "enrollments",
        sa.Column("withdrawn_from_session", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("enrollments") as batch:
        batch.drop_column("withdrawn_from_session")
