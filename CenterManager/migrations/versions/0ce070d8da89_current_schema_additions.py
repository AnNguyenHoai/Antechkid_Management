"""Current schema additions: audit trail.

Revision ID: 0ce070d8da89
Revises: 5ce9314feb37
"""
from alembic import op
import sqlalchemy as sa

revision = "0ce070d8da89"
down_revision = "5ce9314feb37"
branch_labels = None
depends_on = None

_AUDIT_COLUMNS = [
    ("actor_id", sa.Integer()),
    ("actor_name", sa.String(length=100)),
    ("action", sa.String(length=100)),
    ("module", sa.String(length=50)),
    ("target_type", sa.String(length=50)),
    ("target_id", sa.String(length=100)),
    ("target_name", sa.String(length=200)),
    ("result", sa.String(length=20)),
    ("details", sa.Text()),
]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("actor_name", sa.String(length=100), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("module", sa.String(length=50), nullable=False),
            sa.Column("target_type", sa.String(length=50), nullable=True),
            sa.Column("target_id", sa.String(length=100), nullable=True),
            sa.Column("target_name", sa.String(length=200), nullable=True),
            sa.Column("result", sa.String(length=20), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        existing = {column["name"] for column in inspector.get_columns("audit_logs")}
        with op.batch_alter_table("audit_logs") as batch:
            for name, column_type in _AUDIT_COLUMNS:
                if name not in existing:
                    batch.add_column(sa.Column(name, column_type, nullable=True))

    # Create indexes only when absent. This makes upgrade safe for databases
    # that were previously patched by the old startup create_all/ALTER logic.
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("audit_logs")}
    for name, column in [
        ("ix_audit_logs_action", "action"),
        ("ix_audit_logs_actor_id", "actor_id"),
        ("ix_audit_logs_created_at", "created_at"),
        ("ix_audit_logs_module", "module"),
        ("ix_audit_logs_result", "result"),
    ]:
        if name not in existing_indexes:
            op.create_index(name, "audit_logs", [column], unique=False)


def downgrade():
    bind = op.get_bind()
    if "audit_logs" in sa.inspect(bind).get_table_names():
        op.drop_table("audit_logs")
