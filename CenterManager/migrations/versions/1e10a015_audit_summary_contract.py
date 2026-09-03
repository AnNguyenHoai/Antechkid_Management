"""Reconcile the audit log summary contract.

Revision ID: 1e10a015
Revises: 1e10a014

The runtime audit schema requires a non-null summary, while the ORM and audit
service previously omitted it. This migration makes the application contract
explicit and safely upgrades databases created by either the current migration
chain or an older/out-of-band schema that already has a summary column.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a015"
down_revision = "1e10a014"
branch_labels = None
depends_on = None


def _has_table(bind):
    return sa.inspect(bind).has_table("audit_logs")


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind):
        return

    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("audit_logs")}

    if "summary" not in columns:
        # Use a temporary server default so existing rows remain valid while the
        # column is introduced. We replace it with an application-level required
        # field after the data has been backfilled.
        with op.batch_alter_table("audit_logs") as batch:
            batch.add_column(
                sa.Column("summary", sa.String(length=500), nullable=True, server_default="")
            )

        bind.execute(
            sa.text(
                "UPDATE audit_logs SET summary = action "
                "WHERE summary IS NULL OR trim(summary) = ''"
            )
        )

        with op.batch_alter_table("audit_logs") as batch:
            batch.alter_column(
                "summary",
                existing_type=sa.String(length=500),
                nullable=False,
                server_default=None,
            )
    else:
        # Databases patched out-of-band may already have summary. Backfill any
        # nullable/blank legacy rows before enforcing the canonical NOT NULL
        # contract. Existing non-null summaries are preserved verbatim.
        bind.execute(
            sa.text(
                "UPDATE audit_logs SET summary = action "
                "WHERE summary IS NULL OR trim(summary) = ''"
            )
        )
        with op.batch_alter_table("audit_logs") as batch:
            batch.alter_column(
                "summary",
                existing_type=columns["summary"]["type"],
                nullable=False,
            )


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind):
        return

    inspector = sa.inspect(bind)
    if "summary" in {column["name"] for column in inspector.get_columns("audit_logs")}:
        with op.batch_alter_table("audit_logs") as batch:
            batch.drop_column("summary")
