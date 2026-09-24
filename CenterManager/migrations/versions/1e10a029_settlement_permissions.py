"""Add persisted Settlement capabilities and default role grants.

Revision ID: 1e10a029
Revises: 1e10a028

Only permission metadata is upgraded. Existing role customizations and financial
history are preserved. Confirm/reopen are role-derived, never persisted here.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a029"
down_revision = "1e10a028"
branch_labels = None
depends_on = None

# Migration values are frozen so future registry changes cannot alter this upgrade.
_PERMISSIONS = (
    "finance.settlement.view",
    "finance.settlement.create",
    "finance.settlement.update",
)


def upgrade():
    bind = op.get_bind()
    for name in _PERMISSIONS:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO permissions "
                "(name, description, category, created_at, updated_at) "
                "VALUES (:name, :name, 'finance', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"name": name},
        )
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO role_permissions "
                "(role_id, permission_id, created_at, updated_at) "
                "SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
                "FROM roles r CROSS JOIN permissions p "
                "WHERE r.name IN ('admin', 'finance', 'manager') AND p.name = :name"
            ),
            {"name": name},
        )


def downgrade():
    bind = op.get_bind()
    for name in _PERMISSIONS:
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE name = :name)"
            ),
            {"name": name},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE name = :name"),
            {"name": name},
        )
