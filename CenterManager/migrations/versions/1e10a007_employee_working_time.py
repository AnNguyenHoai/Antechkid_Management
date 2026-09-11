"""Employee working time / attendance foundation.
Revision ID: 1e10a007
Revises: 1e10a006
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a007"
down_revision = "1e10a006"
branch_labels = None
depends_on = None

PERMISSIONS = {
    "working_time.view.self": "View own working time",
    "working_time.view.all": "View all employee working time",
    "working_time.create.self": "Book own working time and check in/out",
    "working_time.manage": "Manage and approve employee working time",
    "working_time.lock": "Lock a month's working time",
}

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
    pids = {n: _permission(bind, n, d) for n, d in PERMISSIONS.items()}
    for role in ("teacher", "reception", "finance"):
        for n in ("working_time.view.self", "working_time.create.self"):
            _grant(bind, role, pids[n])
    for role in ("admin", "manager"):
        for n in PERMISSIONS:
            _grant(bind, role, pids[n])

    op.create_table(
        "employee_working_time_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("work_type", sa.String(60), nullable=False, server_default="WORK"),
        sa.Column("source", sa.String(20), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="BOOKED"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_employee_working_time_employee_date", "employee_working_time_entries", ["employee_id", "work_date"])
    op.create_index("ix_employee_working_time_status", "employee_working_time_entries", ["employee_id", "status"])

def downgrade():
    bind = op.get_bind()
    op.drop_index("ix_employee_working_time_status", table_name="employee_working_time_entries")
    op.drop_index("ix_employee_working_time_employee_date", table_name="employee_working_time_entries")
    op.drop_table("employee_working_time_entries")
    for name in PERMISSIONS:
        pid = bind.execute(sa.text("SELECT id FROM permissions WHERE name=:name"), {"name": name}).scalar()
        if pid:
            bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:id"), {"id": pid})
            bind.execute(sa.text("DELETE FROM permissions WHERE id=:id"), {"id": pid})
