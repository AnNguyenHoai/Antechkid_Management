"""Grant teachers own work-registration access.

Revision ID: 1e10a006
Revises: 1e10a005
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a006"
down_revision = "1e10a005"
branch_labels = None
depends_on = None

SELF_PERMISSION = "work_registration.self"
TEACHER_ROLE = "teacher"


def upgrade() -> None:
    bind = op.get_bind()
    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE name=:name"),
        {"name": SELF_PERMISSION},
    ).scalar()
    if not permission_id:
        bind.execute(
            sa.text(
                "INSERT INTO permissions "
                "(name, description, category, created_at, updated_at) "
                "VALUES (:name, :description, 'employee', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "name": SELF_PERMISSION,
                "description": "View and manage own work registration",
            },
        )
        permission_id = bind.execute(
            sa.text("SELECT id FROM permissions WHERE name=:name"),
            {"name": SELF_PERMISSION},
        ).scalar()

    teacher_role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name=:name"),
        {"name": TEACHER_ROLE},
    ).scalar()
    if teacher_role_id and permission_id:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO role_permissions "
                "(role_id, permission_id, created_at, updated_at) "
                "VALUES (:role_id, :permission_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"role_id": teacher_role_id, "permission_id": permission_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE name=:name"),
        {"name": SELF_PERMISSION},
    ).scalar()
    teacher_role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name=:name"),
        {"name": TEACHER_ROLE},
    ).scalar()
    if permission_id and teacher_role_id:
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE role_id=:role_id AND permission_id=:permission_id"
            ),
            {"role_id": teacher_role_id, "permission_id": permission_id},
        )
