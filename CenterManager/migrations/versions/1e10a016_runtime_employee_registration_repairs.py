"""Repair runtime employee registration permissions and employee-document FK.

Revision ID: 1e10a016
Revises: 1e10a015

This migration fixes two production/runtime gaps that can survive a clean test
suite because existing databases may already be at the previous head:
* grant teachers the canonical work_registration.self permission;
* make employee_documents.employee_id ON DELETE CASCADE so deleting an
  employee with only dependent documents does not violate the FK constraint.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a016"
down_revision = "1e10a015"
branch_labels = None
depends_on = None

SELF_PERMISSION = "work_registration.self"
TEACHER_ROLE = "teacher"


def _grant_teacher_self_permission(bind):
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
    if role_id and permission_id:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO role_permissions "
                "(role_id, permission_id, created_at, updated_at) "
                "VALUES (:role_id, :permission_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"role_id": role_id, "permission_id": permission_id},
        )


def _repair_employee_document_fk(bind):
    inspector = sa.inspect(bind)
    if not inspector.has_table("employee_documents"):
        return

    naming_convention = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    }
    with op.batch_alter_table(
        "employee_documents",
        recreate="always",
        naming_convention=naming_convention,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_employee_documents_employee_id_employees",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_employee_documents_employee_id_employees",
            "employees",
            ["employee_id"],
            ["id"],
            ondelete="CASCADE",
        )


def upgrade():
    bind = op.get_bind()
    _grant_teacher_self_permission(bind)
    _repair_employee_document_fk(bind)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("employee_documents"):
        naming_convention = {
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        }
        with op.batch_alter_table(
            "employee_documents",
            recreate="always",
            naming_convention=naming_convention,
        ) as batch_op:
            batch_op.drop_constraint(
                "fk_employee_documents_employee_id_employees",
                type_="foreignkey",
            )
            batch_op.create_foreign_key(
                "fk_employee_documents_employee_id_employees",
                "employees",
                ["employee_id"],
                ["id"],
            )

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
