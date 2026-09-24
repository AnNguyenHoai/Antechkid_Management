"""Add Enrollment tuition snapshot contract fields.

Revision ID: 1e10a031
Revises: 1e10a030

Historical enrollments are intentionally not backfilled from the current Class
contract. The legacy schema did not record the tuition/session terms that were
agreed at enrollment time, so NULL snapshot fields represent an explicit
unresolved historical contract instead of fabricated financial evidence.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a031"
down_revision = "1e10a030"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("enrollments", sa.Column("agreed_course_fee", sa.Numeric(14, 4), nullable=True))
    op.add_column("enrollments", sa.Column("planned_sessions", sa.Integer(), nullable=True))
    op.add_column("enrollments", sa.Column("unit_fee", sa.Numeric(14, 4), nullable=True))
    op.add_column("enrollments", sa.Column("enrolled_from_session", sa.Integer(), nullable=True))
    op.add_column("enrollments", sa.Column("enrolled_until_session", sa.Integer(), nullable=True))
    op.add_column(
        "enrollments",
        sa.Column(
            "discount_amount",
            sa.Numeric(14, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade():
    with op.batch_alter_table("enrollments") as batch_op:
        batch_op.drop_column("discount_amount")
        batch_op.drop_column("enrolled_until_session")
        batch_op.drop_column("enrolled_from_session")
        batch_op.drop_column("unit_fee")
        batch_op.drop_column("planned_sessions")
        batch_op.drop_column("agreed_course_fee")
