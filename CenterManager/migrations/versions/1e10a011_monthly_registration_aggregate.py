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
    op.create_index("ix_employee_work_registration_blocks_registration_id", "employee_work_registration_blocks", ["registration_id"])

    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, employee_id, period_id, work_date, start_time, end_time, work_type, notes, status "
        "FROM employee_work_registrations ORDER BY employee_id, work_date, start_time, id"
    )).mappings().all()
    groups = {}
    for r in rows:
        key = (r["employee_id"], r["period_id"])
        groups.setdefault(key, r)

    for key, first in groups.items():
        status = first["status"]
        # CLOSED was the previous period/block terminal state. Preserve it as
        # accepted at aggregate level; period closure remains represented by the period itself.
        if status == "CLOSED":
            status = "ACCEPTED"
        if status not in ("DRAFT", "SUBMITTED", "ACCEPTED"):
            status = "DRAFT"
        bind.execute(sa.text(
            "UPDATE employee_work_registrations SET status=:status, submitted_at=NULL, accepted_at=NULL, accepted_by_user_id=NULL WHERE id=:id"
        ), {"status": status, "id": first["id"]})
        for r in rows:
            if (r["employee_id"], r["period_id"]) != key:
                continue
            bind.execute(sa.text(
                "INSERT INTO employee_work_registration_blocks "
                "(registration_id, work_date, start_time, end_time, work_type, notes, created_at, updated_at) "
                "VALUES (:registration_id,:work_date,:start_time,:end_time,:work_type,:notes,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ), {"registration_id": first["id"], "work_date": r["work_date"], "start_time": r["start_time"], "end_time": r["end_time"], "work_type": r["work_type"], "notes": r["notes"]})

    for key, first in groups.items():
        bind.execute(sa.text(
            "DELETE FROM employee_work_registrations WHERE employee_id=:employee_id AND period_id=:period_id AND id<>:keep"
        ), {"employee_id": key[0], "period_id": key[1], "keep": first["id"]})

    with op.batch_alter_table("employee_work_registrations") as batch:
        batch.drop_column("work_date")
        batch.drop_column("start_time")
        batch.drop_column("end_time")
        batch.drop_column("work_type")
        batch.drop_column("notes")
        batch.drop_column("created_by_user_id")
        batch.alter_column("period_id", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint("uq_employee_work_registration_employee_period", ["employee_id", "period_id"])


def downgrade():
    raise RuntimeError("Downgrade from monthly work-registration aggregate is not supported.")
