"""Finance voucher attachments metadata (FEAT-003, Issue #579).

Only metadata is stored in SQLite; voucher files are immutable,
content-addressed files outside the database (PO decision D-009).

Revision ID: 1e10a044
Revises: 1e10a043
Create Date: 2026-11-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "1e10a044"
down_revision = "1e10a043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("finance_attachments"):
        op.create_table(
            "finance_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entity_type", sa.String(length=20), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("stored_path", sa.String(length=500), nullable=False),
            sa.Column("mime_type", sa.String(length=50), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("uploaded_by", sa.String(length=100), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
    indexes = {index["name"] for index in inspect(bind).get_indexes("finance_attachments") if index.get("name")}
    if "ix_finance_attachments_entity" not in indexes:
        op.create_index("ix_finance_attachments_entity", "finance_attachments", ["entity_type", "entity_id"])
    if "ix_finance_attachments_sha256" not in indexes:
        op.create_index("ix_finance_attachments_sha256", "finance_attachments", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_finance_attachments_sha256", table_name="finance_attachments")
    op.drop_index("ix_finance_attachments_entity", table_name="finance_attachments")
    op.drop_table("finance_attachments")
