"""Finance period domain foundation.

Revision ID: 1e10a009
Revises: 1e10a008
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a009"
down_revision = "1e10a008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "finance_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("effective_from", name="uq_finance_period_effective_from"),
    )
    op.create_index(
        "ix_finance_period_status_effective_from",
        "finance_periods",
        ["status", "effective_from"],
        unique=False,
    )

    bind = op.get_bind()
    for name, description in [
        ("finance.period.view", "View Finance period configuration."),
        ("finance.period.manage", "Manage Finance period duration configuration (Admin only)."),
    ]:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO permissions "
                "(name, description, category, created_at, updated_at) "
                "VALUES (:name, :description, 'finance', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"name": name, "description": description},
        )

    # Only finance.view-style read access is persisted as a role grant here.
    # finance.period.manage remains an explicit Admin-only authorization policy
    # in the capability layer and is intentionally not granted through roles.
    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'finance.period.view'")
    ).scalar()
    if permission_id:
        for role_name in ("admin", "finance"):
            role_id = bind.execute(
                sa.text("SELECT id FROM roles WHERE name = :name"),
                {"name": role_name},
            ).scalar()
            if role_id:
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
    period_permission_names = ("finance.period.view", "finance.period.manage")
    for name in period_permission_names:
        permission_id = bind.execute(
            sa.text("SELECT id FROM permissions WHERE name = :name"),
            {"name": name},
        ).scalar()
        if permission_id:
            bind.execute(
                sa.text("DELETE FROM role_permissions WHERE permission_id = :permission_id"),
                {"permission_id": permission_id},
            )
            bind.execute(
                sa.text("DELETE FROM permissions WHERE id = :permission_id"),
                {"permission_id": permission_id},
            )
    op.drop_index("ix_finance_period_status_effective_from", table_name="finance_periods")
    op.drop_table("finance_periods")
