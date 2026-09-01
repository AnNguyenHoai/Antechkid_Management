from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "1e10a013_reconcile_monthly_registration_schema.py"
)


def _load_migration():
    spec = spec_from_file_location("migration_1e10a013", MIGRATION_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_pre_013_schema(connection):
    metadata = sa.MetaData()
    sa.Table("employees", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "employee_work_registration_periods",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
    )
    sa.Table(
        "employee_work_registrations",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        # The pre-1e10a013 schema is intentionally modeled as nullable here so
        # the migration can inspect and reject legacy invalid rows before it
        # rebuilds the canonical table with a NOT NULL period_id.
        sa.Column("period_id", sa.Integer(), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("work_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_by_user_id", sa.Integer()),
        sa.Column("reviewed_by_user_id", sa.Integer()),
        sa.Column("submitted_at", sa.DateTime()),
        sa.Column("accepted_at", sa.DateTime()),
        sa.Column("accepted_by_user_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    sa.Table(
        "employee_work_registration_blocks",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("work_type", sa.String(60), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    metadata.create_all(connection)


def _run_upgrade(connection):
    migration = _load_migration()
    migration.op = Operations(MigrationContext.configure(connection))
    migration.upgrade()


def test_reconcile_removes_legacy_columns_and_preserves_aggregate_and_blocks():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _build_pre_013_schema(connection)
        connection.execute(sa.text("INSERT INTO employees (id) VALUES (10)"))
        connection.execute(sa.text("INSERT INTO users (id) VALUES (20)"))
        connection.execute(
            sa.text(
                "INSERT INTO employee_work_registration_periods "
                "(id, year, month) VALUES (30, 2026, 9)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO employee_work_registrations "
                "(id, employee_id, period_id, work_date, start_time, end_time, "
                "work_type, status, submitted_at, accepted_at, accepted_by_user_id, "
                "created_at, updated_at) "
                "VALUES (40, 10, 30, '2026-09-01', '09:00:00', '12:00:00', "
                "'WORK', 'ACCEPTED', '2026-08-25 10:00:00', '2026-08-26 10:00:00', "
                "20, '2026-08-20 10:00:00', '2026-08-26 10:00:00')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO employee_work_registration_blocks "
                "(id, registration_id, work_date, start_time, end_time, work_type, "
                "notes, created_at, updated_at) VALUES "
                "(50, 40, '2026-09-01', '09:00:00', '12:00:00', 'WORK', 'kept', "
                "'2026-08-20 10:00:00', '2026-08-26 10:00:00')"
            )
        )

        _run_upgrade(connection)

        columns = {
            row["name"]
            for row in sa.inspect(connection).get_columns("employee_work_registrations")
        }
        assert columns == {
            "id",
            "employee_id",
            "period_id",
            "status",
            "submitted_at",
            "accepted_at",
            "accepted_by_user_id",
            "created_at",
            "updated_at",
        }

        registration = connection.execute(
            sa.text(
                "SELECT id, employee_id, period_id, status, submitted_at, "
                "accepted_at, accepted_by_user_id FROM employee_work_registrations"
            )
        ).one()
        assert registration[0:4] == (40, 10, 30, "ACCEPTED")
        assert registration[4] is not None
        assert registration[5] is not None
        assert registration[6] == 20

        block = connection.execute(
            sa.text(
                "SELECT id, registration_id, work_date, start_time, end_time, "
                "work_type, notes FROM employee_work_registration_blocks"
            )
        ).one()
        assert block[0:2] == (50, 40)
        assert block[5:] == ("WORK", "kept")

        indexes = {
            index["name"]: index
            for index in sa.inspect(connection).get_indexes(
                "employee_work_registrations"
            )
        }
        assert "ix_employee_work_registrations_period_id" in indexes
        assert "ix_employee_work_registration_status" in indexes
        assert bool(indexes["uq_employee_work_registration_employee_period"]["unique"])


def test_reconcile_refuses_null_period_id_before_schema_change():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _build_pre_013_schema(connection)
        connection.execute(sa.text("INSERT INTO employees (id) VALUES (10)"))
        connection.execute(
            sa.text(
                "INSERT INTO employee_work_registrations "
                "(id, employee_id, period_id, work_date, start_time, end_time, "
                "work_type, status, created_at, updated_at) VALUES "
                "(40, 10, NULL, '2026-09-01', '09:00:00', '12:00:00', 'WORK', "
                "'DRAFT', '2026-08-20 10:00:00', '2026-08-20 10:00:00')"
            )
        )

        with pytest.raises(RuntimeError, match="NULL period_id"):
            _run_upgrade(connection)

        columns = {
            row["name"]
            for row in sa.inspect(connection).get_columns("employee_work_registrations")
        }
        assert "work_date" in columns
        assert "period_id" in columns


def test_reconcile_refuses_orphan_blocks_before_schema_change():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _build_pre_013_schema(connection)
        connection.execute(sa.text("INSERT INTO employees (id) VALUES (10)"))
        connection.execute(
            sa.text(
                "INSERT INTO employee_work_registration_periods "
                "(id, year, month) VALUES (30, 2026, 9)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO employee_work_registrations "
                "(id, employee_id, period_id, work_date, start_time, end_time, "
                "work_type, status, created_at, updated_at) VALUES "
                "(40, 10, 30, '2026-09-01', '09:00:00', '12:00:00', 'WORK', "
                "'DRAFT', '2026-08-20 10:00:00', '2026-08-20 10:00:00')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO employee_work_registration_blocks "
                "(id, registration_id, work_date, start_time, end_time, work_type, "
                "created_at, updated_at) VALUES "
                "(50, 999, '2026-09-01', '09:00:00', '12:00:00', 'WORK', "
                "'2026-08-20 10:00:00', '2026-08-20 10:00:00')"
            )
        )

        with pytest.raises(RuntimeError, match="availability block\(s\) reference"):
            _run_upgrade(connection)

        columns = {
            row["name"]
            for row in sa.inspect(connection).get_columns("employee_work_registrations")
        }
        assert "work_date" in columns
