# -*- coding: utf-8 -*-
"""Regression tests for Alembic migrations and schema contracts."""
from pathlib import Path

import pytest


def _get_migration_files():
    versions_dir = Path(__file__).resolve().parent.parent / "migrations" / "versions"
    if not versions_dir.exists():
        return []
    return [f for f in versions_dir.glob("*.py") if f.name != "__init__.py"]


def _upgrade_to_head(migration_db_path):
    from alembic import command
    from alembic.config import Config

    project_root = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{migration_db_path}")
    command.upgrade(alembic_cfg, "head")
    return alembic_cfg


def test_migration_upgrade(migration_db_path):
    """A fresh database upgrades to the complete schema at Alembic head."""
    migration_files = _get_migration_files()
    if not migration_files:
        pytest.fail("No migration files found.")

    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path

    _upgrade_to_head(migration_db_path)
    engine = create_engine_for_path(migration_db_path)
    inspector = inspect(engine)

    expected_tables = {
        "students", "parents", "enrollments", "assessments",
        "timeline_events", "student_products", "progress", "attachments",
        "employees", "employee_documents",
    }
    actual_tables = set(inspector.get_table_names())
    assert expected_tables.issubset(actual_tables)
    assert "audit_logs" in actual_tables
    assert "alembic_version" in actual_tables


def test_enrollment_reconciliation_columns_exist_at_migration_head(migration_db_path):
    """PR I/J runtime code must never run against a head missing reconciliation lineage."""
    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path

    _upgrade_to_head(migration_db_path)
    engine = create_engine_for_path(migration_db_path)
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("enrollments")
    }
    assert {
        "reconciled_into_enrollment_id",
        "reconciled_at",
        "reconciled_by",
        "reconcile_reason",
        "reconciliation_reviewed_at",
        "reconciliation_reviewed_by",
        "reconciliation_review_reason",
    }.issubset(columns)


def test_existing_database_upgrades_from_1e10a039_without_enrollment_table_rebuild(
    migration_db_path,
):
    """Production path: PR J lineage upgrade must be additive and SQLite-safe."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path

    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{migration_db_path}")

    command.upgrade(cfg, "1e10a039")
    command.upgrade(cfg, "head")

    engine = create_engine_for_path(migration_db_path)
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("enrollments")
    }
    assert "reconciled_into_enrollment_id" in columns
    assert "reconciliation_reviewed_at" in columns


def test_reconciliation_migration_upgrade_avoids_batch_rebuild_and_self_fk():
    migration_source = (
        Path(__file__).resolve().parent.parent
        / "migrations"
        / "versions"
        / "1e10a040_enrollment_reconciliation_lineage.py"
    ).read_text(encoding="utf-8")
    upgrade_source = migration_source.split("def downgrade()", 1)[0]

    assert 'op.add_column(' in upgrade_source
    assert 'op.create_index(' in upgrade_source
    assert 'batch_alter_table("enrollments")' not in upgrade_source
    assert "create_foreign_key" not in upgrade_source
    assert "fk_enrollments_reconciled_into" not in upgrade_source


def test_repair_revision_recovers_stamped_1e10a040_with_missing_physical_columns(
    migration_db_path,
):
    """A database stamped to 1e10a040 but missing PR H/J columns must self-repair."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path

    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{migration_db_path}")

    # Build a legitimate pre-PR-H/J schema, then simulate the production failure
    # mode where revision metadata advanced without all physical columns landing.
    command.upgrade(cfg, "1e10a038")
    command.stamp(cfg, "1e10a040")
    command.upgrade(cfg, "head")

    engine = create_engine_for_path(migration_db_path)
    db_inspector = inspect(engine)
    enrollment_columns = {
        column["name"]
        for column in db_inspector.get_columns("enrollments")
    }
    class_fee_columns = {
        column["name"]
        for column in db_inspector.get_columns("class_fee_history")
    }
    enrollment_indexes = {
        index["name"]
        for index in db_inspector.get_indexes("enrollments")
        if index.get("name")
    }

    assert {
        "reconciled_into_enrollment_id",
        "reconciled_at",
        "reconciled_by",
        "reconcile_reason",
        "reconciliation_reviewed_at",
        "reconciliation_reviewed_by",
        "reconciliation_review_reason",
    }.issubset(enrollment_columns)
    assert "changed_by" in class_fee_columns
    assert "ix_enrollments_reconciled_into_enrollment_id" in enrollment_indexes


def test_production_alembic_env_preserves_application_logging_handlers():
    env_source = (
        Path(__file__).resolve().parent.parent / "migrations" / "env.py"
    ).read_text(encoding="utf-8")

    assert 'config.attributes.get("connection") is None' in env_source
    assert "disable_existing_loggers=False" in env_source


def test_post_upgrade_validation_checks_revision_and_physical_schema():
    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "centermanager"
        / "database"
        / "migration.py"
    ).read_text(encoding="utf-8")

    assert "_validate_post_upgrade_schema(connection, config)" in source
    assert "Database revision is at Alembic head but required physical schema is missing" in source
    assert '"class_fee_history": {"changed_by"}' in source


def test_installed_runtime_migration_requires_maintenance_fence(monkeypatch):
    from centermanager.database import migration

    monkeypatch.setattr(migration, "runtime_db_maintenance_active", lambda: False)

    with pytest.raises(
        RuntimeError,
        match="requires the database maintenance fence",
    ):
        migration.upgrade_installed_runtime_database_under_maintenance_to_head()


def test_employee_timestamp_defaults_and_persistence_after_migration(migration_db_path):
    """Employee inserts must succeed because timestamp defaults exist in DB."""
    from sqlalchemy import inspect
    from sqlalchemy.orm import sessionmaker
    from centermanager.database.engine import create_engine_for_path
    from centermanager.models.employee import Employee

    _upgrade_to_head(migration_db_path)
    engine = create_engine_for_path(migration_db_path)
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("employees")}

    for column_name in ("created_at", "updated_at"):
        assert columns[column_name]["nullable"] is False
        default = columns[column_name]["default"]
        assert default is not None, f"employees.{column_name} must have a database default"
        assert "CURRENT_TIMESTAMP" in str(default).upper()

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        employee = Employee(
            employee_code="EMP-00001",
            full_name="Migration Regression Employee",
            employment_status=Employee.STATUS_ACTIVE,
        )
        session.add(employee)
        session.commit()
        session.refresh(employee)

        assert employee.id is not None
        assert employee.created_at is not None
        assert employee.updated_at is not None


def test_existing_employee_database_upgrades_timestamp_defaults(migration_db_path):
    """A database already at 1e10a002 upgrades safely to the timestamp fix."""
    from alembic import command
    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path

    project_root = Path(__file__).resolve().parent.parent
    from alembic.config import Config
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{migration_db_path}")

    command.upgrade(cfg, "1e10a002")
    command.upgrade(cfg, "head")

    engine = create_engine_for_path(migration_db_path)
    columns = {column["name"]: column for column in inspect(engine).get_columns("employees")}
    for column_name in ("created_at", "updated_at"):
        assert columns[column_name]["default"] is not None
        assert "CURRENT_TIMESTAMP" in str(columns[column_name]["default"]).upper()


def test_migration_downgrade(migration_db_path):
    """The canonical weekly registration schema explicitly does not support downgrade."""
    migration_files = _get_migration_files()
    if not migration_files:
        pytest.fail("No migration files found.")

    from alembic import command

    alembic_cfg = _upgrade_to_head(migration_db_path)
    with pytest.raises(
        RuntimeError,
        match="Weekly work-registration migration is intentionally irreversible because monthly aggregates are split across weeks",
    ):
        command.downgrade(alembic_cfg, "base")


def test_employee_access_permissions_exist_after_migration(migration_db_path):
    """Employee self/all permissions are part of the persisted schema contract."""
    from sqlalchemy import text
    from sqlalchemy import create_engine
    _upgrade_to_head(migration_db_path)
    engine = create_engine(f"sqlite:///{migration_db_path}")
    with engine.connect() as conn:
        names = {
            row[0] for row in conn.execute(
                text("SELECT name FROM permissions WHERE name IN "
                     "('employee.view.self', 'employee.view.all')")
            )
        }
    assert names == {"employee.view.self", "employee.view.all"}
