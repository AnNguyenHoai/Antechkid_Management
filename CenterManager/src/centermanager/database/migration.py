# -*- coding: utf-8 -*-
"""Alembic migration lifecycle for the production runtime database."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from centermanager.database.engine import create_production_engine

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
        database_path = get_paths().database_dir / "center.db"
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(database_path).resolve()}")
    config.set_main_option("script_location", str(_migration_root(project_root)))
    return config


def upgrade_database_to_head() -> None:
    """Upgrade the runtime database to Alembic head.

    Existing pre-Alembic databases are stamped at the legacy baseline only
    when they already contain the historical core schema. New databases are
    upgraded from base normally.
    """
    engine = create_production_engine()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    config = get_alembic_config()
    if "alembic_version" not in tables and _BASELINE_TABLES.intersection(tables):
        logger.info(
            "Legacy database detected without Alembic version; stamping baseline %s",
            "5ce9314feb37",
        )
        command.stamp(config, "5ce9314feb37")

    logger.info("Upgrading database schema to Alembic head")
    command.upgrade(config, "head")
    logger.info("Database schema migration completed successfully")


def get_current_revision() -> str | None:
    config = get_alembic_config()
    from alembic.script import ScriptDirectory
    engine = create_production_engine()
    with engine.connect() as connection:
        context = __import__("alembic.runtime.migration", fromlist=["MigrationContext"]).MigrationContext.configure(connection)
        return context.get_current_revision()


def get_head_revision() -> str:
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(get_alembic_config())
    return script.get_current_head()


def validate_database_at_head() -> bool:
    return get_current_revision() == get_head_revision()
