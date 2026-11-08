"""Add opt-in Tuition Engine V1 schema without reinterpreting historic records.

Revision ID: 1e10a046
Revises: 1e10a045
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "1e10a046"
down_revision = "1e10a045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_tuition_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("monthly_fee_vnd", sa.Integer(), nullable=False),
        sa.Column("schedule_version", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("activated_by", sa.String(100), nullable=True),
        sa.UniqueConstraint("class_id", "month", "version", name="uq_monthly_tuition_plan_version"),
        sa.CheckConstraint("monthly_fee_vnd >= 0", name="ck_monthly_plan_fee_nonnegative"),
        sa.CheckConstraint("version > 0", name="ck_monthly_plan_version_positive"),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'CLOSED')", name="ck_monthly_plan_status"),
    )
    op.create_index("ix_monthly_plan_class", "monthly_tuition_plans", ["class_id"])
    op.create_index("uq_monthly_tuition_active_class_month", "monthly_tuition_plans",
                    ["class_id", "month"], unique=True,
                    sqlite_where=sa.text("status = 'ACTIVE'"))
    op.create_table(
        "monthly_tuition_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("monthly_tuition_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_date", sa.Date(), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.UniqueConstraint("plan_id", "session_id", name="uq_monthly_plan_session"),
        sa.CheckConstraint("amount_vnd >= 0", name="ck_monthly_allocation_nonnegative"),
    )
    op.create_index("ix_monthly_allocation_plan", "monthly_tuition_allocations", ["plan_id"])
    op.create_table(
        "enrollment_monthly_tuition_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=False),
        sa.Column("activated_by", sa.String(100), nullable=False),
        sa.UniqueConstraint("enrollment_id", name="uq_monthly_term_enrollment"),
    )
    op.create_index("ix_monthly_term_enrollment", "enrollment_monthly_tuition_terms", ["enrollment_id"])
    op.create_table(
        "monthly_tuition_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(100), nullable=False),
        sa.UniqueConstraint("enrollment_id", "session_id", name="uq_monthly_outcome_enrollment_session"),
        sa.UniqueConstraint("idempotency_key", name="uq_monthly_outcome_idempotency"),
        sa.CheckConstraint(
            "outcome IN ('BILLABLE', 'RESCHEDULED', 'CENTRE_CANCELLED_NO_MAKEUP')",
            name="ck_monthly_outcome",
        ),
    )
    op.create_index("ix_monthly_outcome_enrollment", "monthly_tuition_outcomes", ["enrollment_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "monthly_tuition_outcomes",
        "enrollment_monthly_tuition_terms",
        "monthly_tuition_allocations",
        "monthly_tuition_plans",
    ):
        count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        if count:
            raise RuntimeError(f"Refusing to remove populated tuition evidence table: {table}")
    op.drop_index("ix_monthly_outcome_enrollment", table_name="monthly_tuition_outcomes")
    op.drop_table("monthly_tuition_outcomes")
    op.drop_index("ix_monthly_term_enrollment", table_name="enrollment_monthly_tuition_terms")
    op.drop_table("enrollment_monthly_tuition_terms")
    op.drop_index("ix_monthly_allocation_plan", table_name="monthly_tuition_allocations")
    op.drop_table("monthly_tuition_allocations")
    op.drop_index("uq_monthly_tuition_active_class_month", table_name="monthly_tuition_plans")
    op.drop_index("ix_monthly_plan_class", table_name="monthly_tuition_plans")
    op.drop_table("monthly_tuition_plans")
