"""Repair/resume employee work-registration aggregate migration.

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


def _unique_indexes(bind, name):
    return {
        i["name"]
        for i in sa.inspect(bind).get_indexes(name)
        if i.get("name") and i.get("unique")
    }


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "employee_work_registrations"):
        raise RuntimeError("employee_work_registrations does not exist")

    columns = _columns(bind, "employee_work_registrations")

    # A previous partial run may have added the aggregate metadata columns.
    # Repair only what is missing; avoid SQLite batch rebuilds.
    for name, sql_type in (
        ("submitted_at", sa.DateTime()),
        ("accepted_at", sa.DateTime()),
        ("accepted_by_user_id", sa.Integer()),
    ):
        if name not in columns:
            op.add_column(
                "employee_work_registrations",
                sa.Column(name, sql_type, nullable=True),
            )

    # The detail table may already exist from a partial execution.
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

    if "ix_employee_work_registration_blocks_registration_id" not in _indexes(
        bind, "employee_work_registration_blocks"
    ):
        op.create_index(
            "ix_employee_work_registration_blocks_registration_id",
            "employee_work_registration_blocks",
            ["registration_id"],
        )

    columns = _columns(bind, "employee_work_registrations")
    legacy = {
        "work_date",
        "start_time",
        "end_time",
        "work_type",
        "notes",
        "reviewed_by_user_id",
        "created_by_user_id",
    }

    # If legacy columns remain, finish data conversion here. This is needed
    # because an interrupted 1e10a011 may have completed some DDL but stopped
    # before copying or cleaning up all rows.
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
                "UPDATE employee_work_registrations "
                "SET status=:status, submitted_at=:submitted_at, "
                "accepted_at=:accepted_at, accepted_by_user_id=:accepted_by_user_id "
                "WHERE id=:id"
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

        # Preserve the first root for each employee/month, then remove duplicate roots.
        for key, first in groups.items():
            bind.execute(sa.text(
                "DELETE FROM employee_work_registrations "
                "WHERE employee_id=:employee_id AND period_id=:period_id AND id<>:keep"
            ), {
                "employee_id": key[0],
                "period_id": key[1],
                "keep": first["id"],
            })

        # The legacy index can reference columns we are about to remove.
        for index_name in (
            "ix_employee_work_registration_employee_date",
            "ix_employee_work_registrations_employee_date",
        ):
            if index_name in _indexes(bind, "employee_work_registrations"):
                op.drop_index(index_name, table_name="employee_work_registrations")

        # 1e10a011 deliberately leaves the legacy columns in place so this
        # repair revision can avoid SQLite table rebuilds. Keep data intact;
        # application code already reads the aggregate + block tables.

    # Final monthly invariant is an ordinary unique SQLite index.
    if "uq_employee_work_registration_employee_period" not in _indexes(bind, "employee_work_registrations"):
        op.create_index(
            "uq_employee_work_registration_employee_period",
            "employee_work_registrations",
            ["employee_id", "period_id"],
            unique=True,
        )


def downgrade():
    raise RuntimeError("Downgrade from registration aggregate repair is not supported.")
