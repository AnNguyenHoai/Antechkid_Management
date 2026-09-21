"""EP-EMP-WEEKLY-02 weekly schedule planning.

Revision ID: 1e10a024
Revises: 1e10a023
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a024"
down_revision = "1e10a023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employee_schedule_weeks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
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
        sa.UniqueConstraint("week_start", name="uq_employee_schedule_week_start"),
    )

    op.create_table(
        "employee_schedule_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "schedule_week_id",
            sa.Integer(),
            sa.ForeignKey("employee_schedule_weeks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False, server_default="MANUAL"),
        sa.Column("note", sa.String(500), nullable=True),
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
        sa.UniqueConstraint(
            "schedule_week_id",
            "employee_id",
            "work_date",
            "start_time",
            "end_time",
            name="uq_employee_schedule_assignment_interval",
        ),
    )
    op.create_index(
        "ix_employee_schedule_assignment_employee_date",
        "employee_schedule_assignments",
        ["employee_id", "work_date"],
    )
    op.create_index(
        "ix_employee_schedule_assignment_week_employee",
        "employee_schedule_assignments",
        ["schedule_week_id", "employee_id"],
    )


def downgrade():
    op.drop_index(
        "ix_employee_schedule_assignment_week_employee",
        table_name="employee_schedule_assignments",
    )
    op.drop_index(
        "ix_employee_schedule_assignment_employee_date",
        table_name="employee_schedule_assignments",
    )
    op.drop_table("employee_schedule_assignments")
    op.drop_table("employee_schedule_weeks")
