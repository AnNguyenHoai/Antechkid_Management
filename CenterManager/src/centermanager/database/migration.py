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

from centermanager.database.encryption import DatabaseKeyStore, database_encryption_required
from centermanager.database.engine import (
    create_engine_for_path,
    create_production_engine,
    get_database_path,
)

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
    """Resolve the authoritative Alembic migration tree.

    Frozen production builds must prefer the migrations embedded in the exact
    executable build.  Release folders also contain an external copy for
    transparency/support, but that copy can become stale when an executable is
    replaced during an incremental rollout.  Allowing a stale external tree to
    override the bundled tree creates a code/schema split-brain.

    Source/dev execution keeps using the checkout's external migrations.
    """
    external = project_root / "migrations"
    bundled = _bundled_root()
    if bundled is not None:
        bundled_migrations = bundled / "migrations"
        if bundled_migrations.exists():
            return bundled_migrations
        raise RuntimeError(
            "Frozen CenterManager build is missing bundled Alembic migrations."
        )
    return external


def _alembic_ini_path(project_root: Path) -> Path:
    """Resolve the Alembic config paired with the authoritative migration tree."""
    external = project_root / "alembic.ini"
    bundled = _bundled_root()
    if bundled is not None:
        bundled_ini = bundled / "alembic.ini"
        if bundled_ini.exists():
            return bundled_ini
        raise RuntimeError(
            "Frozen CenterManager build is missing bundled alembic.ini."
        )
    return external


def get_alembic_config(database_path: Path | None = None) -> Config:
    from centermanager.core.paths import get_paths

    project_root = get_paths().project_root
    ini_path = _alembic_ini_path(project_root)
    migration_root = _migration_root(project_root)
    logger.info(
        "Alembic assets resolved: ini=%s migrations=%s frozen=%s",
        ini_path,
        migration_root,
        bool(_bundled_root()),
    )
    config = Config(str(ini_path))
    if database_path is None:
        database_path = get_database_path()
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(database_path).resolve()}")
    config.set_main_option("script_location", str(migration_root))
    return config


def _upgrade_database_with_engine(database_path: Path, engine) -> None:
    """Upgrade one database using an already-correct SQLAlchemy engine.

    Production passes a SQLCipher-keyed engine. Disposable/dev callers can
    continue to use a plain SQLite engine. Alembic receives the existing
    connection through Config.attributes so it never reopens an encrypted file
    through the plain sqlite driver.

    The connection is transactional on purpose. SQLite DDL itself may be
    non-transactional, but Alembic records the applied revision using DML in
    ``alembic_version``.  Using ``engine.connect()`` here lets SQLAlchemy roll
    that revision write back when the connection closes, leaving a database
    whose tables exist but whose migration history is empty.  The next launch
    then attempts the initial migration again and fails with "table ... already
    exists".  ``engine.begin()`` commits the Alembic revision together with the
    successful migration lifecycle.
    """
    database_path = Path(database_path).resolve()
    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())

        config = get_alembic_config(database_path)
        config.attributes["connection"] = connection

        if "alembic_version" not in tables and _BASELINE_TABLES.intersection(tables):
            logger.info(
                "Legacy database detected without Alembic version; stamping baseline %s",
                "5ce9314feb37",
            )
            command.stamp(config, "5ce9314feb37")

        logger.info("Upgrading database schema to Alembic head: %s", database_path)
        command.upgrade(config, "head")
        logger.info("Database schema migration completed successfully: %s", database_path)


def upgrade_database_path_to_head(database_path: Path) -> None:
    """Upgrade one existing plain/disposable database file to Alembic head."""
    database_path = Path(database_path).resolve()
    engine = create_engine_for_path(database_path, allow_create=False)
    try:
        _upgrade_database_with_engine(database_path, engine)
    finally:
        engine.dispose()


def upgrade_fresh_runtime_database_to_head() -> None:
    """Migrate the explicit first-run runtime container to Alembic head.

    This narrow entry point exists only for controlled initialization after
    ``initialize_runtime_database()`` has created the empty DB container and,
    in production, provisioned its workspace key. It intentionally bypasses
    the normal lifecycle ``AVAILABLE`` gate because a brand-new container has
    no tables yet and is therefore ``INVALID_SCHEMA`` by operational rules.

    Normal startup and normal production engines remain fail-closed.
    """
    database_path = get_database_path()
    if not database_path.is_file() or database_path.stat().st_size == 0:
        raise RuntimeError("Fresh runtime database container is missing or empty")

    encrypted = database_encryption_required()
    key = DatabaseKeyStore().load() if encrypted else None
    engine = create_engine_for_path(
        database_path,
        allow_create=True,
        encrypted=encrypted,
        encryption_key=key,
    )
    try:
        _upgrade_database_with_engine(database_path, engine)
    finally:
        engine.dispose()


def upgrade_database_to_head() -> None:
    """Upgrade an operational canonical runtime DB using the active engine."""
    database_path = get_database_path()
    engine = create_production_engine(echo=False)
    try:
        _upgrade_database_with_engine(database_path, engine)
    finally:
        engine.dispose()


def get_current_revision(database_path: Path | None = None) -> str | None:
    """Return the Alembic revision for an existing database path."""
    if database_path is None:
        engine = create_production_engine(echo=False)
    else:
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
