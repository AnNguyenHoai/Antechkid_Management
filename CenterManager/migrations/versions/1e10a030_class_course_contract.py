"""Add Class course/tuition contract fields.

Revision ID: 1e10a030
Revises: 1e10a029

Historical ``classes.fee`` is copied to ``course_fee`` because it is direct
recorded monetary evidence. Duration/session metadata is intentionally left NULL:
the old schema did not record enough information to reconstruct it safely.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a030"
down_revision = "1e10a029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("classes", sa.Column("course_fee", sa.Integer(), nullable=True))
    op.add_column("classes", sa.Column("duration_months", sa.Integer(), nullable=True))
    op.add_column("classes", sa.Column("planned_sessions", sa.Integer(), nullable=True))
    op.add_column("classes", sa.Column("sessions_per_week", sa.Integer(), nullable=True))

    # Preserve only evidence the legacy schema actually recorded. Do not infer
    # duration, planned sessions, frequency, or a synthetic end date.
    op.execute(
        sa.text(
            "UPDATE classes SET course_fee = fee "
            "WHERE course_fee IS NULL AND fee IS NOT NULL"
        )
    )


def downgrade():
    with op.batch_alter_table("classes") as batch_op:
        batch_op.drop_column("sessions_per_week")
        batch_op.drop_column("planned_sessions")
        batch_op.drop_column("duration_months")
        batch_op.drop_column("course_fee")
