"""Employee profile self-update permission.

Revision ID: 1e10a005
Revises: 1e10a004
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a005"
down_revision = "1e10a004"
branch_labels = None
depends_on = None

SELF_UPDATE = "employee.update.self"

def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "INSERT OR IGNORE INTO permissions "
        "(name, description, category, created_at, updated_at) "
        "VALUES (:name, :description, 'employee', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    ), {"name": SELF_UPDATE, "description": "Update own employee profile"})

    perm_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE name=:name"), {"name": SELF_UPDATE}
    ).scalar()
    if not perm_id:
        return

    for role_name in ("teacher", "reception", "finance"):
        role_id = bind.execute(
            sa.text("SELECT id FROM roles WHERE name=:name"), {"name": role_name}
        ).scalar()
        if role_id:
            bind.execute(sa.text(
                "INSERT OR IGNORE INTO role_permissions "
                "(role_id, permission_id, created_at, updated_at) "
                "VALUES (:role_id, :permission_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ), {"role_id": role_id, "permission_id": perm_id})

def downgrade() -> None:
    bind = op.get_bind()
    perm_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE name=:name"), {"name": SELF_UPDATE}
    ).scalar()
    if perm_id:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:id"), {"id": perm_id})
        bind.execute(sa.text("DELETE FROM permissions WHERE id=:id"), {"id": perm_id})
