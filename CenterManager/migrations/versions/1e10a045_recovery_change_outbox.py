"""RV-02: transactional recovery operation outbox.

Revision ID: 1e10a045
Revises: 1e10a044
Create Date: 2026-11-05

Additive schema only. Existing authoritative business data is unchanged.
The migration is performed under the existing Git MAIN install/SQLCipher
maintenance authority, never in an ordinary READ transaction.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "1e10a045"
down_revision = "1e10a044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("recovery_change_outbox"):
        op.create_table(
            "recovery_change_outbox",
            sa.Column("event_id", sa.String(36), primary_key=True),
            sa.Column("operation_id", sa.String(36), nullable=False),
            sa.Column("write_session_id", sa.String(128), nullable=False),
            sa.Column("base_main_oid", sa.String(64), nullable=False),
            sa.Column("occurred_at_utc", sa.DateTime(), nullable=False),
            sa.Column("actor_id", sa.String(100), nullable=True),
            sa.Column("module", sa.String(60), nullable=False),
            sa.Column("action", sa.String(60), nullable=False),
            sa.Column("entity_type", sa.String(80), nullable=False),
            sa.Column("entity_id", sa.String(100), nullable=True),
            sa.Column("summary_code", sa.String(120), nullable=False),
            sa.Column("summary_args_json", sa.Text(), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False),
        )
    names = {row.get("name") for row in inspect(bind).get_indexes("recovery_change_outbox")}
    if "ix_recovery_outbox_session" not in names:
        op.create_index("ix_recovery_outbox_session", "recovery_change_outbox",
                        ["write_session_id", "occurred_at_utc"])
    if "ix_recovery_outbox_operation" not in names:
        op.create_index("ix_recovery_outbox_operation", "recovery_change_outbox", ["operation_id"], unique=True)


def downgrade() -> None:
    # Never silently remove unresolved edit history in a routine downgrade.
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM recovery_change_outbox")).scalar_one()
    if count:
        raise RuntimeError("Recovery Change Log contains events; preserve an encrypted backup before downgrade.")
    op.drop_index("ix_recovery_outbox_operation", table_name="recovery_change_outbox")
    op.drop_index("ix_recovery_outbox_session", table_name="recovery_change_outbox")
    op.drop_table("recovery_change_outbox")
