"""Repair partially-applied employee registration aggregate migration.

Revision ID: 1e10a012
Revises: 1e10a011
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a012"
down_revision = "1e10a011"
branch_labels = None
depends_on = None


def _table_exists(bind, name):
    return sa.inspect(bind).has_table(name)


def _columns(bind, name):
    return {c["name"] for c in sa.inspect(bind).get_columns(name)}


def _indexes(bind, name):
    return {i["name"] for i in sa.inspect(bind).get_indexes(name) if i.get("name")}


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "employee_work_registrations"):
        raise RuntimeError("employee_work_registrations does not exist")

    # The previous revision can be left half-applied because SQLite DDL is
    # non-transactional. At this point the table may already contain the new
    # aggregate columns and/or the block table. Repair the observable schema
    # without repeating destructive data migration.
    columns = _columns(bind, "employee_work_registrations")
    with op.batch_alter_table("employee_work_registrations") as batch:
        if "submitted_at" not in columns:
            batch.add_column(sa.Column("submitted_at", sa.DateTime(), nullable=True))
        if "accepted_at" not in columns:
            batch.add_column(sa.Column("accepted_at", sa.DateTime(), nullable=True))
        if "accepted_by_user_id" not in columns:
            batch.add_column(sa.Column("accepted_by_user_id", sa.Integer(), nullable=True))

    if not _table_exists(bind, "employee_work_registration_blocks"):
        op.create_table(
            "employee_work_registration_blocks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("registration_id", sa.Integer(), sa.ForeignKey("employee_work_registrations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("work_type", sa.String(60), nullable=False, server_default="WORK"),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if "ix_employee_work_registration_blocks_registration_id" not in _indexes(bind, "employee_work_registration_blocks"):
        op.create_index(
            "ix_employee_work_registration_blocks_registration_id",
            "employee_work_registration_blocks",
            ["registration_id"],
        )

    # Complete only the schema cleanup when legacy columns are still present.
    # Data conversion is deliberately delegated to 1e10a011; this revision
    # exists to recover from a partial DDL state without double-copying rows.
    columns = _columns(bind, "employee_work_registrations")
    legacy = [
        c for c in (
            "work_date",
            "start_time",
            "end_time",
            "work_type",
            "notes",
            "created_by_user_id",
            "reviewed_by_user_id",
        )
        if c in columns
    ]
    if legacy:
        raise RuntimeError(
            "1e10a011 left legacy registration columns in place. "
            "Run from a clean checkout/database or inspect 1e10a011 before retrying."
        )


def downgrade():
    raise RuntimeError("Downgrade from registration aggregate repair is not supported.")
