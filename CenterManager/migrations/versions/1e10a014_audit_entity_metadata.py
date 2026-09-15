"""Add canonical entity metadata to audit logs.

Revision ID: 1e10a014
Revises: 1e10a013

The audit contract uses entity_type/entity_id as the canonical identity while
retaining target_* for backwards compatibility. Existing audit rows are kept
unchanged; the new columns are nullable so this migration is safe for legacy
rows and for databases that already contain the columns from an out-of-band
schema update.
"""
from alembic import op
import sqlalchemy as sa

revision = "1e10a014"
down_revision = "1e10a013"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("audit_logs"):
        return

    existing = {column["name"] for column in inspector.get_columns("audit_logs")}
    with op.batch_alter_table("audit_logs") as batch:
        if "entity_type" not in existing:
            batch.add_column(sa.Column("entity_type", sa.String(length=50), nullable=True))
        if "entity_id" not in existing:
            batch.add_column(sa.Column("entity_id", sa.String(length=100), nullable=True))

    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("audit_logs")}
    for name, column in [
        ("ix_audit_logs_entity_type", "entity_type"),
        ("ix_audit_logs_entity_id", "entity_id"),
    ]:
        if name not in existing_indexes:
            op.create_index(name, "audit_logs", [column], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("audit_logs"):
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes("audit_logs")}
    for name in ("ix_audit_logs_entity_id", "ix_audit_logs_entity_type"):
        if name in existing_indexes:
            op.drop_index(name, table_name="audit_logs")

    existing = {column["name"] for column in inspector.get_columns("audit_logs")}
    with op.batch_alter_table("audit_logs") as batch:
        if "entity_id" in existing:
            batch.drop_column("entity_id")
        if "entity_type" in existing:
            batch.drop_column("entity_type")
