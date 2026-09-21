"""EP-EMP-WEEKLY-03 schedule publish, freeze and audit lifecycle.

Revision ID: 1e10a025
Revises: 1e10a024
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a025"
down_revision = "1e10a024"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("employee_schedule_weeks") as batch:
        batch.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(sa.Column("published_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("published_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("frozen_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("frozen_by_user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_employee_schedule_week_published_by",
            "users",
            ["published_by_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_employee_schedule_week_frozen_by",
            "users",
            ["frozen_by_user_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("employee_schedule_weeks") as batch:
        batch.drop_constraint(
            "fk_employee_schedule_week_frozen_by", type_="foreignkey"
        )
        batch.drop_constraint(
            "fk_employee_schedule_week_published_by", type_="foreignkey"
        )
        batch.drop_column("frozen_by_user_id")
        batch.drop_column("frozen_at")
        batch.drop_column("published_by_user_id")
        batch.drop_column("published_at")
        batch.drop_column("version")
