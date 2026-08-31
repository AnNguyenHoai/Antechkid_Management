# -*- coding: utf-8 -*-
"""
Tests for Alembic migrations.
"""
import pytest
from pathlib import Path

def _get_migration_files():
    """Trả về danh sách các file migration (file .py trong migrations/versions)."""
    versions_dir = Path(__file__).resolve().parent.parent / "migrations" / "versions"
    if not versions_dir.exists():
        return []
    return [f for f in versions_dir.glob("*.py") if f.name != "__init__.py"]

def test_migration_upgrade(test_db_path):
    """Test that initial migration creates the schema at Alembic head."""
    migration_files = _get_migration_files()
    if not migration_files:
        pytest.fail("No migration files found. Run 'alembic revision --autogenerate -m \"Initial schema\"' first.")

    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db_path}")

    command.upgrade(alembic_cfg, "head")

    engine = create_engine_for_path(test_db_path)
    inspector = inspect(engine)

    expected_tables = {
        "students", "parents", "enrollments", "assessments",
        "timeline_events", "student_products", "progress", "attachments"
    }
    actual_tables = set(inspector.get_table_names())
    assert expected_tables.issubset(actual_tables)
    assert "audit_logs" in actual_tables
    assert "alembic_version" in actual_tables


def test_migration_downgrade(test_db_path):
    """Test that migration downgrade works."""
    migration_files = _get_migration_files()
    if not migration_files:
        pytest.fail("No migration files found. Run 'alembic revision --autogenerate -m \"Initial schema\"' first.")

    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db_path}")

    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")

    engine = create_engine_for_path(test_db_path)
    inspector = inspect(engine)
    domain_tables = {
        "students", "parents", "enrollments", "assessments",
        "timeline_events", "student_products", "progress", "attachments"
    }
    assert not domain_tables.intersection(set(inspector.get_table_names()))