"""New monthly-class policy for fresh enrollment, preserving all legacy classes.

Revision ID: 1e10a047
Revises: 1e10a046
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a047"
down_revision = "1e10a046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_class_defaults",
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("monthly_fee_vnd", sa.Integer(), nullable=False),
        sa.Column("effective_month", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("weekly_days", sa.String(30), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.CheckConstraint("monthly_fee_vnd >= 0", name="ck_monthly_class_fee_nonnegative"),
    )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM monthly_class_defaults")).scalar_one()
    if count:
        raise RuntimeError("Refusing to remove active monthly class policies")
    op.drop_table("monthly_class_defaults")
