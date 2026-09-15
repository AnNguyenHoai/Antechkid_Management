"""Work registration business model permissions and CLOSED status.
Revision ID: 1e10a009
Revises: 1e10a008
"""
from alembic import op
import sqlalchemy as sa
revision="1e10a009"; down_revision="1e10a008"; branch_labels=None; depends_on=None
PERMISSIONS = {
    "work_registration.self": "Create and manage the authenticated employee's next-month availability",
    "work_registration.view.all": "View all employee work registrations for planning",
    "work_registration.manage": "Close submitted employee work registrations after planning",
}

def upgrade():
    bind=op.get_bind()
    for name, desc in PERMISSIONS.items():
        bind.execute(sa.text("INSERT OR IGNORE INTO permissions (name, description, category, created_at, updated_at) VALUES (:n,:d,'employee',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"n":name,"d":desc})
    # All employee roles receive self registration. Admin/Manager receive all/manage.
    for role in ("admin","manager","teacher","reception","finance"):
        rid=bind.execute(sa.text("SELECT id FROM roles WHERE name=:n"),{"n":role}).scalar()
        if not rid: continue
        pid=bind.execute(sa.text("SELECT id FROM permissions WHERE name='work_registration.self'")).scalar()
        if pid: bind.execute(sa.text("INSERT OR IGNORE INTO role_permissions (role_id,permission_id,created_at,updated_at) VALUES (:r,:p,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"r":rid,"p":pid})
        if role in ("admin","manager"):
            for name in ("work_registration.view.all","work_registration.manage"):
                p=bind.execute(sa.text("SELECT id FROM permissions WHERE name=:n"),{"n":name}).scalar()
                if p: bind.execute(sa.text("INSERT OR IGNORE INTO role_permissions (role_id,permission_id,created_at,updated_at) VALUES (:r,:p,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{"r":rid,"p":p})

def downgrade():
    bind=op.get_bind()
    for name in PERMISSIONS:
        pid=bind.execute(sa.text("SELECT id FROM permissions WHERE name=:n"),{"n":name}).scalar()
        if pid:
            bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:p"),{"p":pid})
            bind.execute(sa.text("DELETE FROM permissions WHERE id=:p"),{"p":pid})
