"""Work registration period lifecycle and integrity hardening.
Revision ID: 1e10a010
Revises: 1e10a009
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a010"
down_revision = "1e10a009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employee_work_registration_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("submission_deadline", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("year", "month", name="uq_employee_work_registration_period_month"),
    )
    op.add_column(
        "employee_work_registrations",
        sa.Column("period_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_employee_work_registrations_period_id", "employee_work_registrations", ["period_id"])
    # Backfill a period for every historical registration month.
    bind = op.get_bind()
    months = bind.execute(sa.text(
        "SELECT DISTINCT CAST(strftime('%Y', work_date) AS INTEGER), "
        "CAST(strftime('%m', work_date) AS INTEGER) "
        "FROM employee_work_registrations"
    )).fetchall()
    for year, month in months:
        bind.execute(sa.text(
            "INSERT OR IGNORE INTO employee_work_registration_periods "
            "(year, month, status, created_at, updated_at) "
            "VALUES (:y, :m, 'OPEN', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"y": year, "m": month})
    bind.execute(sa.text(
        "UPDATE employee_work_registrations SET period_id = "
        "(SELECT p.id FROM employee_work_registration_periods p "
        "WHERE p.year = CAST(strftime('%Y', employee_work_registrations.work_date) AS INTEGER) "
        "AND p.month = CAST(strftime('%m', employee_work_registrations.work_date) AS INTEGER)) "
        "WHERE period_id IS NULL"
    ))


def downgrade():
    op.drop_index("ix_employee_work_registrations_period_id", table_name="employee_work_registrations")
    op.drop_column("employee_work_registrations", "period_id")
    op.drop_table("employee_work_registration_periods")
