"""Employee schedule foundation: recurring rules and date exceptions.
Revision ID: 1e10a006
Revises: 1e10a005
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a006"
down_revision = "1e10a005"
branch_labels = None
depends_on = None

SELF = "schedule.view.self"
ALL = "schedule.view.all"
MANAGE = "schedule.manage"

def _permission(bind, name, description):
    bind.execute(sa.text(
        "INSERT OR IGNORE INTO permissions (name, description, category, created_at, updated_at) "
        "VALUES (:name, :description, 'employee', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    ), {"name": name, "description": description})
    return bind.execute(sa.text("SELECT id FROM permissions WHERE name=:name"), {"name": name}).scalar()

def _grant(bind, role_name, permission_id):
    role_id = bind.execute(sa.text("SELECT id FROM roles WHERE name=:name"), {"name": role_name}).scalar()
    if role_id and permission_id:
        bind.execute(sa.text(
            "INSERT OR IGNORE INTO role_permissions (role_id, permission_id, created_at, updated_at) "
            "VALUES (:role_id, :permission_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"role_id": role_id, "permission_id": permission_id})

def upgrade():
    bind = op.get_bind()
    p_self = _permission(bind, SELF, "View own employee schedule")
    p_all = _permission(bind, ALL, "View all employee schedules")
    p_manage = _permission(bind, MANAGE, "Create, update and delete employee schedules")
    for role in ("teacher", "reception", "finance"):
        _grant(bind, role, p_self)
    for role in ("admin", "manager"):
        _grant(bind, role, p_all)
        _grant(bind, role, p_manage)
    op.create_table(
        "employee_schedule_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_employee_schedule_rules_employee_day", "employee_schedule_rules", ["employee_id", "day_of_week"])
    op.create_index("ix_employee_schedule_rules_effective", "employee_schedule_rules", ["employee_id", "effective_from", "effective_to"])
    op.create_table(
        "employee_schedule_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("exception_type", sa.String(20), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("employee_id", "schedule_date", name="uq_employee_schedule_exception_date"),
    )
    op.create_index("ix_employee_schedule_exceptions_employee_date", "employee_schedule_exceptions", ["employee_id", "schedule_date"])

def downgrade():
    bind = op.get_bind()
    op.drop_index("ix_employee_schedule_exceptions_employee_date", table_name="employee_schedule_exceptions")
    op.drop_table("employee_schedule_exceptions")
    op.drop_index("ix_employee_schedule_rules_effective", table_name="employee_schedule_rules")
    op.drop_index("ix_employee_schedule_rules_employee_day", table_name="employee_schedule_rules")
    op.drop_table("employee_schedule_rules")
    for name in (SELF, ALL, MANAGE):
        pid = bind.execute(sa.text("SELECT id FROM permissions WHERE name=:name"), {"name": name}).scalar()
        if pid:
            bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:id"), {"id": pid})
            bind.execute(sa.text("DELETE FROM permissions WHERE id=:id"), {"id": pid})
