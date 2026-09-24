"""Add effective-dated Class fee history for tuition obligations.

Revision ID: 1e10a028
Revises: 1e10a027
Create Date: 2026-09-24
"""
from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from alembic import op

revision = "1e10a028"
down_revision = "1e10a027"
branch_labels = None
depends_on = None

_TABLE = "class_fee_history"
_CLASS_INDEX = "ix_class_fee_history_class_id"
_DATE_INDEX = "ix_class_fee_history_effective_from"
_CUTOVER_DATE = date(2026, 9, 24)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("fee", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="CLASS_FEE_CHANGE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], name="fk_class_fee_history_class_id_classes", ondelete="RESTRICT"),
    )
    op.create_index(_CLASS_INDEX, _TABLE, ["class_id"], unique=False)
    op.create_index(_DATE_INDEX, _TABLE, ["effective_from"], unique=False)

    # Legacy classes have no trustworthy pre-cutover fee provenance. Preserve
    # the fee known at schema cutover only; NEVER project it backward to the
    # class start date. Earlier periods are explicit FW2-09 reconciliation work.
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, fee FROM classes")).mappings()
    history = sa.table(
        _TABLE,
        sa.column("class_id", sa.Integer()),
        sa.column("effective_from", sa.Date()),
        sa.column("fee", sa.Integer()),
        sa.column("source", sa.String()),
    )
    for row in rows:
        bind.execute(history.insert().values(
            class_id=row["id"], effective_from=_CUTOVER_DATE,
            fee=row["fee"], source="MIGRATION_BASELINE",
        ))


def downgrade() -> None:
    op.drop_index(_DATE_INDEX, table_name=_TABLE)
    op.drop_index(_CLASS_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
