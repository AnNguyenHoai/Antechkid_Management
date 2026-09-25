"""TUITION-17: harden Enrollment transfer concurrency and idempotency.

Revision ID: 1e10a038
Revises: 1e10a037
"""
from alembic import op
import sqlalchemy as sa


revision = "1e10a038"
down_revision = "1e10a037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("enrollment_transfers") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(length=120), nullable=True))

    op.execute(
        sa.text(
            "UPDATE enrollment_transfers "
            "SET idempotency_key = 'source-enrollment:' || source_enrollment_id "
            "WHERE idempotency_key IS NULL"
        )
    )

    with op.batch_alter_table("enrollment_transfers") as batch:
        batch.alter_column("idempotency_key", existing_type=sa.String(length=120), nullable=False)
        batch.create_unique_constraint(
            "uq_enrollment_transfer_source", ["source_enrollment_id"]
        )
        batch.create_unique_constraint(
            "uq_enrollment_transfer_idempotency_key", ["idempotency_key"]
        )

    # A student may have historical enrollments in the same class, but only one
    # ACTIVE contract. SQLite and PostgreSQL both support this partial unique
    # index, which closes transfer/create races at the database boundary.
    op.create_index(
        "uq_enrollments_active_student_class",
        "enrollments",
        ["student_id", "class_id"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE' AND class_id IS NOT NULL"),
        postgresql_where=sa.text("status = 'ACTIVE' AND class_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_enrollments_active_student_class", table_name="enrollments")
    with op.batch_alter_table("enrollment_transfers") as batch:
        batch.drop_constraint("uq_enrollment_transfer_idempotency_key", type_="unique")
        batch.drop_constraint("uq_enrollment_transfer_source", type_="unique")
        batch.drop_column("idempotency_key")
