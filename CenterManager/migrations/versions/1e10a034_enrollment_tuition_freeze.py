"""TUITION-12: add auditable Enrollment tuition freeze ranges.

Revision ID: 1e10a034
Revises: 1e10a033

Freeze history is session-range based and intentionally independent from
accounting periods. No historical freeze is inferred during migration.
"""
from alembic import op
import sqlalchemy as sa


revision = "1e10a034"
down_revision = "1e10a033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrollment_freezes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "enrollment_id",
            sa.Integer(),
            sa.ForeignKey("enrollments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("start_session", sa.Integer(), nullable=False),
        sa.Column("end_session", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("resumed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("resume_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("resumed_by", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint("start_session >= 1", name="ck_enrollment_freeze_start_positive"),
        sa.CheckConstraint(
            "end_session IS NULL OR end_session >= start_session",
            name="ck_enrollment_freeze_end_not_before_start",
        ),
    )
    op.create_index(
        "ix_enrollment_freezes_enrollment_id",
        "enrollment_freezes",
        ["enrollment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_enrollment_freezes_enrollment_id", table_name="enrollment_freezes")
    op.drop_table("enrollment_freezes")
