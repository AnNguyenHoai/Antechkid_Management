# -*- coding: utf-8 -*-
"""Regression tests for Alembic migrations and schema contracts."""
from pathlib import Path

import pytest


def _get_migration_files():
    versions_dir = Path(__file__).resolve().parent.parent / "migrations" / "versions"
    if not versions_dir.exists():
        return []
    return [f for f in versions_dir.glob("*.py") if f.name != "__init__.py"]


def _upgrade_to_head(test_db_path):
    from alembic import command
    from alembic.config import Config

    project_root = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db_path}")
    command.upgrade(alembic_cfg, "head")
    return alembic_cfg


def test_migration_upgrade(test_db_path):
    """A fresh database upgrades to the complete schema at Alembic head."""
    migration_files = _get_migration_files()
    if not migration_files:
        pytest.fail("No migration files found.")

    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path

    _upgrade_to_head(test_db_path)
    engine = create_engine_for_path(test_db_path)
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


def test_employee_timestamp_defaults_and_persistence_after_migration(test_db_path):
    """Employee inserts must succeed because timestamp defaults exist in DB."""
    from sqlalchemy import inspect, text
    from sqlalchemy.orm import sessionmaker
    from centermanager.database.engine import create_engine_for_path
    from centermanager.models.employee import Employee

    _upgrade_to_head(test_db_path)
    engine = create_engine_for_path(test_db_path)
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



def test_existing_employee_database_upgrades_timestamp_defaults(test_db_path):
    """A database already at 1e10a002 upgrades safely to the timestamp fix."""
    from alembic import command
    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path

    project_root = Path(__file__).resolve().parent.parent
    from alembic.config import Config
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db_path}")

    command.upgrade(cfg, "1e10a002")
    command.upgrade(cfg, "head")

    engine = create_engine_for_path(test_db_path)
    columns = {column["name"]: column for column in inspect(engine).get_columns("employees")}
    for column_name in ("created_at", "updated_at"):
        assert columns[column_name]["default"] is not None
        assert "CURRENT_TIMESTAMP" in str(columns[column_name]["default"]).upper()

def test_migration_downgrade(test_db_path):
    """Migration downgrade to base removes domain tables, including Employee."""
    migration_files = _get_migration_files()
    if not migration_files:
        pytest.fail("No migration files found.")

    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path
    from alembic import command

    alembic_cfg = _upgrade_to_head(test_db_path)
    command.downgrade(alembic_cfg, "base")

    engine = create_engine_for_path(test_db_path)
    inspector = inspect(engine)
    domain_tables = {
        "students", "parents", "enrollments", "assessments",
        "timeline_events", "student_products", "progress", "attachments",
        "employees", "employee_documents",
    }
    assert not domain_tables.intersection(set(inspector.get_table_names()))


def test_employee_access_permissions_exist_after_migration(test_db_path):
    """Employee self/all permissions are part of the persisted schema contract."""
    from sqlalchemy import text
    from sqlalchemy import create_engine
    _upgrade_to_head(test_db_path)
    engine = create_engine(f"sqlite:///{test_db_path}")
    with engine.connect() as conn:
        names = {
            row[0] for row in conn.execute(
                text("SELECT name FROM permissions WHERE name IN "
                     "('employee.view.self', 'employee.view.all')")
            )
        }
    assert names == {"employee.view.self", "employee.view.all"}
