"""Employee next-month work registration.
Revision ID: 1e10a008
Revises: 1e10a007
"""
from alembic import op
import sqlalchemy as sa
revision="1e10a008"; down_revision="1e10a007"; branch_labels=None; depends_on=None
PERM="working_time.registration.self"
def upgrade():
    bind=op.get_bind()
    bind.execute(sa.text("INSERT OR IGNORE INTO permissions (name, description, category, created_at, updated_at) VALUES (:n,:d,'employee',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"n":PERM,"d":"Register proposed working time for next month"})
    pid=bind.execute(sa.text("SELECT id FROM permissions WHERE name=:n"),{"n":PERM}).scalar()
    for role in ("teacher","reception","finance"):
        rid=bind.execute(sa.text("SELECT id FROM roles WHERE name=:n"),{"n":role}).scalar()
        if rid and pid: bind.execute(sa.text("INSERT OR IGNORE INTO role_permissions (role_id,permission_id,created_at,updated_at) VALUES (:r,:p,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"r":rid,"p":pid})
    for role in ("admin","manager"):
        rid=bind.execute(sa.text("SELECT id FROM roles WHERE name=:n"),{"n":role}).scalar()
        if rid and pid: bind.execute(sa.text("INSERT OR IGNORE INTO role_permissions (role_id,permission_id,created_at,updated_at) VALUES (:r,:p,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"r":rid,"p":pid})
    op.create_table("employee_work_registrations",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("employee_id",sa.Integer(),sa.ForeignKey("employees.id",ondelete="CASCADE"),nullable=False),
        sa.Column("work_date",sa.Date(),nullable=False), sa.Column("start_time",sa.Time(),nullable=False), sa.Column("end_time",sa.Time(),nullable=False),
        sa.Column("work_type",sa.String(60),nullable=False,server_default="WORK"), sa.Column("status",sa.String(20),nullable=False,server_default="DRAFT"),
        sa.Column("notes",sa.String(500),nullable=True), sa.Column("created_by_user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=True),
        sa.Column("reviewed_by_user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=True), sa.Column("created_at",sa.DateTime(),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at",sa.DateTime(),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_employee_work_registration_employee_date","employee_work_registrations",["employee_id","work_date"])
    op.create_index("ix_employee_work_registration_status","employee_work_registrations",["employee_id","status"])
def downgrade():
    op.drop_index("ix_employee_work_registration_status",table_name="employee_work_registrations");op.drop_index("ix_employee_work_registration_employee_date",table_name="employee_work_registrations");op.drop_table("employee_work_registrations")
