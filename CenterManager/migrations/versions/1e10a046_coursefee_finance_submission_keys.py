"""Durable opt-in duplicate-submission fences for Income and Expense.

Revision ID: 1e10a046
Revises: 1e10a045

Course-fee branch: no monthly tuition migration dependency.\nHistorical Income/Expense rows retain NULL keys; new keyed submissions are
unique per ledger, preventing repeated Save after uncertain UI/transport results.
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "1e10a046"
down_revision = "1e10a045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in ("incomes", "expenses"):
        columns = {column["name"] for column in inspect(bind).get_columns(table)}
        if "idempotency_key" not in columns:
            op.add_column(table, sa.Column("idempotency_key", sa.String(120), nullable=True))
        index_name = f"ux_{table}_idempotency_key"
        indexes = {idx["name"] for idx in inspect(bind).get_indexes(table)}
        if index_name not in indexes:
            op.create_index(index_name, table, ["idempotency_key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("expenses", "incomes"):
        if bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE idempotency_key IS NOT NULL")).scalar_one():
            raise RuntimeError(f"Refusing to discard live {table} submission identity")
        index_name = f"ux_{table}_idempotency_key"
        if index_name in {idx["name"] for idx in inspect(bind).get_indexes(table)}:
            op.drop_index(index_name, table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("idempotency_key")
