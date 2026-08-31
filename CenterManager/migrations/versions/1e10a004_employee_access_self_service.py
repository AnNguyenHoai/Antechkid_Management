"""Employee access and self-service permissions.

Revision ID: 1e10a004
Revises: 1e10a003
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a004"
down_revision = "1e10a003"
branch_labels = None
depends_on = None

SELF = "employee.view.self"
ALL = "employee.view.all"
LEGACY = "employee.view"


def _permission_id(bind, name):
    return bind.execute(sa.text("SELECT id FROM permissions WHERE name=:name"), {"name": name}).scalar()


def upgrade() -> None:
    bind = op.get_bind()
    now = sa.text("CURRENT_TIMESTAMP")
    permissions = [
        (SELF, "View own employee profile", "employee"),
        (ALL, "View all employee profiles", "employee"),
    ]
    for name, description, category in permissions:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO permissions "
                "(name, description, category, created_at, updated_at) "
                "VALUES (:name, :description, :category, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"name": name, "description": description, "category": category},
        )

    # Existing system roles: manager gets all employee visibility; other
    # employee-enabled roles get self visibility. Admin already bypasses RBAC.
    for role_name in ("manager",):
        role_id = bind.execute(sa.text("SELECT id FROM roles WHERE name=:name"), {"name": role_name}).scalar()
        perm_id = _permission_id(bind, ALL)
        if role_id and perm_id:
            bind.execute(
                sa.text("INSERT OR IGNORE INTO role_permissions "
                        "(role_id, permission_id, created_at, updated_at) "
                        "VALUES (:role_id, :permission_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {"role_id": role_id, "permission_id": perm_id},
            )

    for role_name in ("teacher", "reception", "finance"):
        role_id = bind.execute(sa.text("SELECT id FROM roles WHERE name=:name"), {"name": role_name}).scalar()
        perm_id = _permission_id(bind, SELF)
        if role_id and perm_id:
            bind.execute(
                sa.text("INSERT OR IGNORE INTO role_permissions "
                        "(role_id, permission_id, created_at, updated_at) "
                        "VALUES (:role_id, :permission_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {"role_id": role_id, "permission_id": perm_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    self_id = _permission_id(bind, SELF)
    all_id = _permission_id(bind, ALL)
    if self_id:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:id"), {"id": self_id})
    if all_id:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:id"), {"id": all_id})
    bind.execute(
        sa.text("DELETE FROM permissions WHERE name IN (:self, :all)"),
        {"self": SELF, "all": ALL},
    )
