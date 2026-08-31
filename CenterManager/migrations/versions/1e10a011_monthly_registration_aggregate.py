"""Convert employee work registration from block rows to monthly aggregates.
Revision ID: 1e10a011
Revises: 1e10a010
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a011"
down_revision = "1e10a010"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    return sa.inspect(bind).has_table(table_name)


def _columns(bind, table_name):
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name):
    return {
        index["name"]
        for index in sa.inspect(bind).get_indexes(table_name)
        if index.get("name")
    }


def _unique_exists(bind, table_name, constraint_name):
    inspector = sa.inspect(bind)
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(bind, "employee_work_registrations"):
        raise RuntimeError(
            "Cannot migrate employee_work_registrations: source table does not exist."
        )

    columns = _columns(bind, "employee_work_registrations")

    # Legacy schema may contain indexes over columns that this migration drops.
    # Remove them before batch_alter_table rebuilds the source table.
    for index_name in (
        "ix_employee_work_registration_employee_date",
        "ix_employee_work_registrations_employee_date",
    ):
        if index_name in _index_names(bind, "employee_work_registrations"):
            op.drop_index(index_name, table_name="employee_work_registrations")

    # This migration is deliberately resumable. A previous execution may have
    # added these aggregate columns before failing during later DDL.
    aggregate_columns = (
        ("submitted_at", sa.DateTime()),
        ("accepted_at", sa.DateTime()),
        ("accepted_by_user_id", sa.Integer()),
    )
    missing_aggregate_columns = [
        (name, column_type)
        for name, column_type in aggregate_columns
        if name not in columns
    ]
    if missing_aggregate_columns:
        with op.batch_alter_table("employee_work_registrations") as batch:
            for name, column_type in missing_aggregate_columns:
                batch.add_column(sa.Column(name, column_type, nullable=True))
        columns = _columns(bind, "employee_work_registrations")

    # The block table can already exist when a previous non-transactional DDL
    # execution stopped after CREATE TABLE. Never recreate it in that case.
    if not _table_exists(bind, "employee_work_registration_blocks"):
        op.create_table(
            "employee_work_registration_blocks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "registration_id",
                sa.Integer(),
                sa.ForeignKey("employee_work_registrations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("work_type", sa.String(60), nullable=False, server_default="WORK"),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if "ix_employee_work_registration_blocks_registration_id" not in _index_names(
        bind, "employee_work_registration_blocks"
    ):
        op.create_index(
            "ix_employee_work_registration_blocks_registration_id",
            "employee_work_registration_blocks",
            ["registration_id"],
        )

    # If the legacy block columns still exist, migrate them. Use NOT EXISTS so
    # rerunning after a partial failure cannot duplicate block rows.
    columns = _columns(bind, "employee_work_registrations")
    legacy_columns = {
        "work_date",
        "start_time",
        "end_time",
        "work_type",
        "notes",
        "reviewed_by_user_id",
        "created_by_user_id",
    }
    if legacy_columns.issubset(columns):
        rows = bind.execute(
            sa.text(
                "SELECT id, employee_id, period_id, work_date, start_time, end_time, "
                "work_type, notes, status, reviewed_by_user_id, created_at, updated_at "
                "FROM employee_work_registrations "
                "ORDER BY employee_id, period_id, work_date, start_time, id"
            )
        ).mappings().all()

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

            bind.execute(
                sa.text(
                    "UPDATE employee_work_registrations "
                    "SET status=:status, submitted_at=:submitted_at, "
                    "accepted_at=:accepted_at, accepted_by_user_id=:accepted_by_user_id "
                    "WHERE id=:id"
                ),
                {
                    "status": status,
                    "submitted_at": submitted_at,
                    "accepted_at": accepted_at,
                    "accepted_by_user_id": accepted_by,
                    "id": first["id"],
                },
            )

            for row in rows:
                if (row["employee_id"], row["period_id"]) != key:
                    continue
                exists = bind.execute(
                    sa.text(
                        "SELECT 1 FROM employee_work_registration_blocks "
                        "WHERE registration_id=:registration_id "
                        "AND work_date=:work_date AND start_time=:start_time "
                        "AND end_time=:end_time AND work_type=:work_type "
                        "AND COALESCE(notes, '')=COALESCE(:notes, '') LIMIT 1"
                    ),
                    {
                        "registration_id": first["id"],
                        "work_date": row["work_date"],
                        "start_time": row["start_time"],
                        "end_time": row["end_time"],
                        "work_type": row["work_type"],
                        "notes": row["notes"],
                    },
                ).first()
                if exists is None:
                    bind.execute(
                        sa.text(
                            "INSERT INTO employee_work_registration_blocks "
                            "(registration_id, work_date, start_time, end_time, work_type, notes, created_at, updated_at) "
                            "VALUES (:registration_id,:work_date,:start_time,:end_time,:work_type,:notes,:created_at,:updated_at)"
                        ),
                        {
                            "registration_id": first["id"],
                            "work_date": row["work_date"],
                            "start_time": row["start_time"],
                            "end_time": row["end_time"],
                            "work_type": row["work_type"],
                            "notes": row["notes"],
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        },
                    )

        # Only remove duplicate roots after all legacy rows are represented in
        # the retained monthly aggregate.
        for key, first in groups.items():
            bind.execute(
                sa.text(
                    "DELETE FROM employee_work_registrations "
                    "WHERE employee_id=:employee_id AND period_id=:period_id AND id<>:keep"
                ),
                {"employee_id": key[0], "period_id": key[1], "keep": first["id"]},
            )

        # Drop legacy columns only after the data migration has completed.
        with op.batch_alter_table("employee_work_registrations") as batch:
            for column_name in (
                "work_date",
                "start_time",
                "end_time",
                "work_type",
                "notes",
                "created_by_user_id",
                "reviewed_by_user_id",
            ):
                batch.drop_column(column_name)
            batch.alter_column("period_id", existing_type=sa.Integer(), nullable=False)

    # The unique constraint is the final schema invariant. Add it only if it
    # is not already present, so a retry after partial DDL is safe.
    if not _unique_exists(
        bind,
        "employee_work_registrations",
        "uq_employee_work_registration_employee_period",
    ):
        with op.batch_alter_table("employee_work_registrations") as batch:
            batch.create_unique_constraint(
                "uq_employee_work_registration_employee_period",
                ["employee_id", "period_id"],
            )


def downgrade():
    raise RuntimeError("Downgrade from monthly work-registration aggregate is not supported.")
