"""EP-FIN-06 income lifecycle and void audit metadata.

Revision ID: 1e10a022
Revises: 1e10a021
"""
from alembic import op
import sqlalchemy as sa


revision = "1e10a022"
down_revision = "1e10a021"
branch_labels = None
depends_on = None


def _column_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()
    columns = _column_names(bind, "incomes")

    with op.batch_alter_table("incomes") as batch:
        if "status" not in columns:
            batch.add_column(
                sa.Column(
                    "status",
                    sa.String(length=20),
                    nullable=False,
                    server_default="ACTIVE",
                )
            )
        if "voided_at" not in columns:
            batch.add_column(sa.Column("voided_at", sa.DateTime(), nullable=True))
        if "voided_by" not in columns:
            batch.add_column(
                sa.Column("voided_by", sa.String(length=100), nullable=True)
            )
        if "void_reason" not in columns:
            batch.add_column(sa.Column("void_reason", sa.Text(), nullable=True))

    indexes = _index_names(bind, "incomes")
    if "ix_incomes_status" not in indexes:
        op.create_index("ix_incomes_status", "incomes", ["status"], unique=False)


def downgrade():
    bind = op.get_bind()
    indexes = _index_names(bind, "incomes")
    if "ix_incomes_status" in indexes:
        op.drop_index("ix_incomes_status", table_name="incomes")

    columns = _column_names(bind, "incomes")
    with op.batch_alter_table("incomes") as batch:
        for column_name in ("void_reason", "voided_by", "voided_at", "status"):
            if column_name in columns:
                batch.drop_column(column_name)
