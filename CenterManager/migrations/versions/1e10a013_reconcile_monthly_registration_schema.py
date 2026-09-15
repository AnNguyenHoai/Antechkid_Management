"""Reconcile employee work registrations with the monthly aggregate schema.

Revision ID: 1e10a013
Revises: 1e10a012

The R2-C application model treats ``employee_work_registrations`` as a
monthly aggregate root and stores availability details in
``employee_work_registration_blocks``. Revisions 1e10a011/1e10a012 migrated
the data but intentionally retained the legacy block columns on the aggregate
table to avoid an SQLite table rebuild. Those NOT NULL legacy columns now
prevent creation of a new aggregate row because the application no longer
provides values for them.

This revision performs the final schema reconciliation with an explicit
SQLite table replacement. Data is copied only for canonical aggregate fields;
availability details remain in the block table. The migration validates the
preconditions before changing the schema and preserves the existing primary
keys, status/timestamp metadata, and monthly uniqueness invariant.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a013"
down_revision = "1e10a012"
branch_labels = None
depends_on = None

REGISTRATION_TABLE = "employee_work_registrations"
NEW_REGISTRATION_TABLE = "employee_work_registrations_new"
BLOCK_TABLE = "employee_work_registration_blocks"
PERIOD_TABLE = "employee_work_registration_periods"
UNIQUE_INDEX = "uq_employee_work_registration_employee_period"
PERIOD_INDEX = "ix_employee_work_registrations_period_id"
STATUS_INDEX = "ix_employee_work_registration_status"


def _table_exists(bind, name):
    return sa.inspect(bind).has_table(name)


def _columns(bind, table):
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {
        index["name"]
        for index in sa.inspect(bind).get_indexes(table)
        if index.get("name")
    }


def _foreign_keys(bind, table):
    return sa.inspect(bind).get_foreign_keys(table)


def _assert_no_null_period_ids(bind):
    count = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {REGISTRATION_TABLE} "
            "WHERE period_id IS NULL"
        )
    ).scalar_one()
    if count:
        raise RuntimeError(
            f"Cannot reconcile registration schema: {count} registration(s) have NULL period_id"
        )


def _assert_periods_exist(bind):
    count = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {REGISTRATION_TABLE} r "
            f"LEFT JOIN {PERIOD_TABLE} p ON p.id = r.period_id "
            "WHERE p.id IS NULL"
        )
    ).scalar_one()
    if count:
        raise RuntimeError(
            f"Cannot reconcile registration schema: {count} registration(s) reference a missing period"
        )


def _assert_monthly_uniqueness(bind):
    duplicates = bind.execute(
        sa.text(
            f"SELECT employee_id, period_id, COUNT(*) AS n "
            f"FROM {REGISTRATION_TABLE} "
            "GROUP BY employee_id, period_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicates:
        raise RuntimeError(
            "Cannot reconcile registration schema: duplicate employee/period aggregate roots remain"
        )


def _assert_blocks_have_registrations(bind):
    if not _table_exists(bind, BLOCK_TABLE):
        raise RuntimeError(
            "Cannot reconcile registration schema: employee_work_registration_blocks does not exist"
        )
    count = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {BLOCK_TABLE} b "
            f"LEFT JOIN {REGISTRATION_TABLE} r ON r.id = b.registration_id "
            "WHERE r.id IS NULL"
        )
    ).scalar_one()
    if count:
        raise RuntimeError(
            f"Cannot reconcile registration schema: {count} availability block(s) reference a missing registration"
        )


def _drop_index_if_exists(bind, name):
    if name in _indexes(bind, REGISTRATION_TABLE):
        op.drop_index(name, table_name=REGISTRATION_TABLE)


def _create_canonical_table():
    return op.create_table(
        NEW_REGISTRATION_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey(PERIOD_TABLE + ".id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "accepted_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, REGISTRATION_TABLE):
        raise RuntimeError(
            "Cannot reconcile registration schema: employee_work_registrations does not exist"
        )
    if not _table_exists(bind, PERIOD_TABLE):
        raise RuntimeError(
            "Cannot reconcile registration schema: employee_work_registration_periods does not exist"
        )
    if not _table_exists(bind, BLOCK_TABLE):
        raise RuntimeError(
            "Cannot reconcile registration schema: employee_work_registration_blocks does not exist"
        )

    columns = _columns(bind, REGISTRATION_TABLE)
    required = {
        "id",
        "employee_id",
        "period_id",
        "status",
        "submitted_at",
        "accepted_at",
        "accepted_by_user_id",
        "created_at",
        "updated_at",
    }
    missing = required - columns
    if missing:
        raise RuntimeError(
            "Cannot reconcile registration schema: missing canonical columns "
            + ", ".join(sorted(missing))
        )

    # Refuse to discard any data that the previous repair migration should
    # already have normalized.
    _assert_no_null_period_ids(bind)
    _assert_periods_exist(bind)
    _assert_monthly_uniqueness(bind)
    _assert_blocks_have_registrations(bind)

    # A leftover _new table indicates an interrupted/manual migration. Refuse
    # to overwrite it because doing so could hide data from an operator.
    if _table_exists(bind, NEW_REGISTRATION_TABLE):
        raise RuntimeError(
            f"Cannot reconcile registration schema: {NEW_REGISTRATION_TABLE} already exists"
        )

    # Disable SQLite FK enforcement while replacing the parent table. Existing
    # block rows are retained unchanged and are validated above. Foreign key
    # enforcement is restored before the migration returns.
    foreign_keys_were_enabled = bind.execute(sa.text("PRAGMA foreign_keys")).scalar()
    if foreign_keys_were_enabled:
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    try:
        _create_canonical_table()

        bind.execute(
            sa.text(
                f"INSERT INTO {NEW_REGISTRATION_TABLE} "
                "(id, employee_id, period_id, status, submitted_at, accepted_at, "
                "accepted_by_user_id, created_at, updated_at) "
                f"SELECT id, employee_id, period_id, status, submitted_at, accepted_at, "
                f"accepted_by_user_id, created_at, updated_at FROM {REGISTRATION_TABLE}"
            )
        )

        bind.execute(sa.text(f"DROP TABLE {REGISTRATION_TABLE}"))
        bind.execute(
            sa.text(
                f"ALTER TABLE {NEW_REGISTRATION_TABLE} "
                f"RENAME TO {REGISTRATION_TABLE}"
            )
        )
    finally:
        if foreign_keys_were_enabled:
            bind.execute(sa.text("PRAGMA foreign_keys=ON"))

    # Recreate only the indexes required by the canonical schema. The old
    # date index was already removed by 1e10a011/1e10a012.
    indexes = _indexes(bind, REGISTRATION_TABLE)
    if PERIOD_INDEX not in indexes:
        op.create_index(PERIOD_INDEX, REGISTRATION_TABLE, ["period_id"])
    if STATUS_INDEX not in indexes:
        op.create_index(STATUS_INDEX, REGISTRATION_TABLE, ["employee_id", "status"])
    if UNIQUE_INDEX not in indexes:
        op.create_index(
            UNIQUE_INDEX,
            REGISTRATION_TABLE,
            ["employee_id", "period_id"],
            unique=True,
        )

    # Verify that the replacement really has no legacy block columns and that
    # all block references still resolve after the table swap.
    final_columns = _columns(bind, REGISTRATION_TABLE)
    legacy = {
        "work_date",
        "start_time",
        "end_time",
        "work_type",
        "notes",
        "created_by_user_id",
        "reviewed_by_user_id",
    }
    unexpected = final_columns & legacy
    if unexpected:
        raise RuntimeError(
            "Registration schema reconciliation failed; legacy columns remain: "
            + ", ".join(sorted(unexpected))
        )
    _assert_blocks_have_registrations(bind)


def downgrade():
    raise RuntimeError(
        "Downgrade from the canonical monthly registration schema is not supported."
    )
