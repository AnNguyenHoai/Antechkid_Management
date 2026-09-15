"""Repair teacher work-registration self access for existing databases.

Revision ID: 1e10a017
Revises: 1e10a016

Some installations can already be at 1e10a016 while their teacher role was
created or restored afterwards. Keep the permission repair idempotent at the
next schema head so runtime login never depends on the seeder having run.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a017"
down_revision = "1e10a016"
branch_labels = None
depends_on = None

SELF_PERMISSION = "work_registration.self"
TEACHER_ROLE = "teacher"


def upgrade():
    bind = op.get_bind()

    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE name=:name"),
        {"name": SELF_PERMISSION},
    ).scalar()

    if permission_id is None:
        bind.execute(
            sa.text(
                "INSERT INTO permissions "
                "(name, description, category, created_at, updated_at) "
                "VALUES (:name, :description, 'employee', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "name": SELF_PERMISSION,
                "description": "Create and manage the authenticated employee's own work registration",
            },
        )
        permission_id = bind.execute(
            sa.text("SELECT id FROM permissions WHERE name=:name"),
            {"name": SELF_PERMISSION},
        ).scalar()

    role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name=:name"),
        {"name": TEACHER_ROLE},
    ).scalar()

    if role_id is not None and permission_id is not None:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO role_permissions "
                "(role_id, permission_id, created_at, updated_at) "
                "VALUES (:role_id, :permission_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"role_id": role_id, "permission_id": permission_id},
        )


def downgrade():
    bind = op.get_bind()
    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE name=:name"),
        {"name": SELF_PERMISSION},
    ).scalar()
    role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name=:name"),
        {"name": TEACHER_ROLE},
    ).scalar()

    if role_id is not None and permission_id is not None:
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE role_id=:role_id AND permission_id=:permission_id"
            ),
            {"role_id": role_id, "permission_id": permission_id},
        )
