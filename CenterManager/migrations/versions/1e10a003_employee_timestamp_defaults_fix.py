"""Fix employee timestamp server defaults.

Revision ID: 1e10a003
Revises: 1e10a002
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a003"
down_revision = "1e10a002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Align the existing employees table with TimestampMixin's DB contract."""
    with op.batch_alter_table("employees", recreate="always") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )


def downgrade() -> None:
    """Restore the pre-fix schema (no database-side timestamp defaults)."""
    with op.batch_alter_table("employees", recreate="always") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=None,
        )
