"""Convert employee work registration from block rows to monthly aggregates.

Revision ID: 1e10a011
Revises: 1e10a010

This revision intentionally avoids SQLite batch table rebuilds.  Startup uses
non-transactional SQLite DDL, so the migration must be safe to resume after a
partial execution.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a011"
down_revision = "1e10a010"
branch_labels = None
depends_on = None


def _table_exists(bind, name):
    return sa.inspect(bind).has_table(name)


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {i["name"] for i in sa.inspect(bind).get_indexes(table) if i.get("name")}


def _unique_index_exists(bind, name):
    return name in _indexes(bind, "employee_work_registrations")


def _add_column(bind, table, name, sql_type):
    if name not in _columns(bind, table):
        op.add_column(table, sa.Column(name, sql_type, nullable=True))


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "employee_work_registrations"):
        raise RuntimeError("Cannot migrate: employee_work_registrations does not exist")

    # 1. Add aggregate metadata without batch_alter_table.  SQLite can perform
    # these ADD COLUMN operations safely and they are independently resumable.
    _add_column(bind, "employee_work_registrations", "submitted_at", sa.DateTime())
    _add_column(bind, "employee_work_registrations", "accepted_at", sa.DateTime())
    _add_column(bind, "employee_work_registrations", "accepted_by_user_id", sa.Integer())

    # 2. Create the detail/block table if this migration was never started or
    # if a previous non-transactional run stopped after table creation.
    if not _table_exists(bind, "employee_work_registration_blocks"):
        op.create_table(
            "employee_work_registration_blocks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("registration_id", sa.Integer(), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("work_type", sa.String(60), nullable=False, server_default="WORK"),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    # Do not fail if the index was created by a previous partial execution.
    if "ix_employee_work_registration_blocks_registration_id" not in _indexes(bind, "employee_work_registration_blocks"):
        op.create_index(
            "ix_employee_work_registration_blocks_registration_id",
            "employee_work_registration_blocks",
            ["registration_id"],
        )

    columns = _columns(bind, "employee_work_registrations")
    legacy = {"work_date", "start_time", "end_time", "work_type", "notes", "reviewed_by_user_id", "created_by_user_id"}

    # 3. Convert legacy rows to one monthly aggregate root per employee/period.
    # Keep the legacy columns in place for this revision. Removing columns with
    # SQLite batch rebuild is the fragile operation that caused startup failure;
    # later application cleanup can remove them once the migration is stable.
    if legacy.issubset(columns):
        rows = bind.execute(sa.text(
            "SELECT id, employee_id, period_id, work_date, start_time, end_time, "
            "work_type, notes, status, reviewed_by_user_id, created_at, updated_at "
            "FROM employee_work_registrations "
            "ORDER BY employee_id, period_id, work_date, start_time, id"
        )).mappings().all()

        groups = {}
        for row in rows:
            groups.setdefault((row["employee_id"], row["period_id"]), row)

        for key, first in groups.items():
            status = first["status"]
            if status == "CLOSED":
                status = "ACCEPTED"
            elif status not in ("DRAFT", "SUBMITTED", "ACCEPTED"):
                status = "DRAFT"

            accepted_by = first["reviewed_by_user_id"] if status == "ACCEPTED" else None
            accepted_at = first["updated_at"] if status == "ACCEPTED" else None
            submitted_at = first["updated_at"] if status in ("SUBMITTED", "ACCEPTED") else None

            bind.execute(sa.text(
                "UPDATE employee_work_registrations SET status=:status, "
                "submitted_at=:submitted_at, accepted_at=:accepted_at, "
                "accepted_by_user_id=:accepted_by_user_id WHERE id=:id"
            ), {
                "status": status,
                "submitted_at": submitted_at,
                "accepted_at": accepted_at,
                "accepted_by_user_id": accepted_by,
                "id": first["id"],
            })

            for row in rows:
                if (row["employee_id"], row["period_id"]) != key:
                    continue
                exists = bind.execute(sa.text(
                    "SELECT 1 FROM employee_work_registration_blocks "
                    "WHERE registration_id=:registration_id AND work_date=:work_date "
                    "AND start_time=:start_time AND end_time=:end_time "
                    "AND work_type=:work_type "
                    "AND COALESCE(notes,'')=COALESCE(:notes,'') LIMIT 1"
                ), {
                    "registration_id": first["id"],
                    "work_date": row["work_date"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "work_type": row["work_type"],
                    "notes": row["notes"],
                }).first()
                if exists is None:
                    bind.execute(sa.text(
                        "INSERT INTO employee_work_registration_blocks "
                        "(registration_id,work_date,start_time,end_time,work_type,notes,created_at,updated_at) "
                        "VALUES (:registration_id,:work_date,:start_time,:end_time,:work_type,:notes,:created_at,:updated_at)"
                    ), {
                        "registration_id": first["id"],
                        "work_date": row["work_date"],
                        "start_time": row["start_time"],
                        "end_time": row["end_time"],
                        "work_type": row["work_type"],
                        "notes": row["notes"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    })

        # Only delete duplicate aggregate roots after all their details have
        # been copied to the retained first root.
        for key, first in groups.items():
            bind.execute(sa.text(
                "DELETE FROM employee_work_registrations "
                "WHERE employee_id=:employee_id AND period_id=:period_id AND id<>:keep"
            ), {"employee_id": key[0], "period_id": key[1], "keep": first["id"]})

    # 4. Remove obsolete indexes only when they still exist.  Do this last so
    # an interrupted run can restart without depending on their presence.
    for name in (
        "ix_employee_work_registration_employee_date",
        "ix_employee_work_registrations_employee_date",
    ):
        if name in _indexes(bind, "employee_work_registrations"):
            op.drop_index(name, table_name="employee_work_registrations")

    # 5. Enforce the monthly invariant with a unique INDEX rather than an
    # ALTER TABLE constraint. SQLite supports this operation directly and it
    # is safe to retry. Existing duplicate roots were collapsed above.
    if not _unique_index_exists(bind, "uq_employee_work_registration_employee_period"):
        op.create_index(
            "uq_employee_work_registration_employee_period",
            "employee_work_registrations",
            ["employee_id", "period_id"],
            unique=True,
        )


def downgrade():
    raise RuntimeError("Downgrade from monthly work-registration aggregate is not supported.")
