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


def upgrade():
    bind = op.get_bind()

    # The 1e10a008 -> 1e10a010 schema contains the legacy block columns but
    # does not contain the aggregate approval timestamps. Add those columns
    # before converting the existing rows so the migration is valid against
    # every database that has actually reached 1e10a010.
    with op.batch_alter_table("employee_work_registrations") as batch:
        batch.add_column(sa.Column("submitted_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("accepted_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("accepted_by_user_id", sa.Integer(), nullable=True))

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
    op.create_index(
        "ix_employee_work_registration_blocks_registration_id",
        "employee_work_registration_blocks",
        ["registration_id"],
    )

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
        key = (row["employee_id"], row["period_id"])
        groups.setdefault(key, row)

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
            bind.execute(
                sa.text(
                    "INSERT INTO employee_work_registration_blocks "
                    "(registration_id, work_date, start_time, end_time, work_type, notes, created_at, updated_at) "
                    "VALUES (:registration_id, :work_date, :start_time, :end_time, :work_type, :notes, :created_at, :updated_at)"
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

    # Remove duplicate legacy roots only after every row has been copied into
    # the retained monthly aggregate.
    for key, first in groups.items():
        bind.execute(
            sa.text(
                "DELETE FROM employee_work_registrations "
                "WHERE employee_id=:employee_id AND period_id=:period_id AND id<>:keep"
            ),
            {"employee_id": key[0], "period_id": key[1], "keep": first["id"]},
        )

    with op.batch_alter_table("employee_work_registrations") as batch:
        batch.drop_column("work_date")
        batch.drop_column("start_time")
        batch.drop_column("end_time")
        batch.drop_column("work_type")
        batch.drop_column("notes")
        batch.drop_column("created_by_user_id")
        batch.drop_column("reviewed_by_user_id")
        batch.alter_column("period_id", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint(
            "uq_employee_work_registration_employee_period",
            ["employee_id", "period_id"],
        )


def downgrade():
    raise RuntimeError("Downgrade from monthly work-registration aggregate is not supported.")
