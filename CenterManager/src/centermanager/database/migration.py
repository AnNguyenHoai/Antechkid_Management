# -*- coding: utf-8 -*-
"""Alembic migration lifecycle for the production runtime database."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from centermanager.database.engine import create_engine_for_path, get_database_path

logger = logging.getLogger(__name__)

_BASELINE_TABLES = {
    "students", "parents", "enrollments", "assessments",
    "timeline_events", "student_products", "progress", "attachments",
}


def _bundled_root() -> Path | None:
    """Return PyInstaller's extracted resource root when running frozen."""
    if not getattr(sys, "frozen", False):
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def _migration_root(project_root: Path) -> Path:
    """Resolve Alembic migrations from the external release or PyInstaller bundle."""
    external = project_root / "migrations"
    if external.exists():
        return external
    bundled = _bundled_root()
    if bundled is not None and (bundled / "migrations").exists():
        return bundled / "migrations"
    return external


def _alembic_ini_path(project_root: Path) -> Path:
    """Resolve alembic.ini from the external release or PyInstaller bundle."""
    external = project_root / "alembic.ini"
    if external.exists():
        return external
    bundled = _bundled_root()
    if bundled is not None and (bundled / "alembic.ini").exists():
        return bundled / "alembic.ini"
    return external


def get_alembic_config(database_path: Path | None = None) -> Config:
    from centermanager.core.paths import get_paths

    project_root = get_paths().project_root
    config = Config(str(_alembic_ini_path(project_root)))
    if database_path is None:
        database_path = get_database_path()
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(database_path).resolve()}")
    config.set_main_option("script_location", str(_migration_root(project_root)))
    return config


def upgrade_database_path_to_head(database_path: Path) -> None:
    """Upgrade one existing database file to the current Alembic head.

    The caller owns the path. This is the canonical migration implementation
    used both by the production runtime database and by the pre-release real-DB
    upgrade gate. The helper never creates a missing database implicitly.
    """
    database_path = Path(database_path).resolve()
    engine = create_engine_for_path(database_path, allow_create=False)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    finally:
        engine.dispose()

    config = get_alembic_config(database_path)
    if "alembic_version" not in tables and _BASELINE_TABLES.intersection(tables):
        logger.info(
            "Legacy database detected without Alembic version; stamping baseline %s",
            "5ce9314feb37",
        )
        command.stamp(config, "5ce9314feb37")

    logger.info("Upgrading database schema to Alembic head: %s", database_path)
    command.upgrade(config, "head")
    logger.info("Database schema migration completed successfully: %s", database_path)


def upgrade_database_to_head() -> None:
    """Upgrade the canonical production runtime database to Alembic head."""
    upgrade_database_path_to_head(get_database_path())


def get_current_revision(database_path: Path | None = None) -> str | None:
    """Return the Alembic revision for an existing database path."""
    if database_path is None:
        database_path = get_database_path()
    engine = create_engine_for_path(Path(database_path), allow_create=False)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()
    finally:
        engine.dispose()


def get_head_revision(database_path: Path | None = None) -> str:
    """Return the migration script head used for the supplied database context."""
    script = ScriptDirectory.from_config(get_alembic_config(database_path))
    return script.get_current_head()


def validate_database_at_head(database_path: Path | None = None) -> bool:
    """Return True only when the selected database is at the current head."""
    return get_current_revision(database_path) == get_head_revision(database_path)
