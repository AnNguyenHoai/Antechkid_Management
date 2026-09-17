# -*- coding: utf-8 -*-
import logging
import sqlite3
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from centermanager.core.paths import get_paths
from centermanager.database.lifecycle import DatabaseLifecycle, DatabaseLifecycleError, DatabaseLifecycleState

logger = logging.getLogger(__name__)


def get_database_path() -> Path:
    """Return the runtime database path without creating the database file."""
    return get_paths().database_dir / "center.db"


def create_engine_for_path(
    db_path: Path,
    echo: bool = False,
    *,
    allow_create: bool = True,
) -> Engine:
    """Create a SQLite engine for a specific path.

    ``allow_create=True`` preserves the low-level helper's historical test and
    bootstrap behavior. Production runtime creation must go through
    ``create_production_engine()``, which always passes ``allow_create=False``
    and therefore rejects a missing database instead of silently materializing
    a new empty one.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    mode = "rwc" if allow_create else "rw"
    database_uri = f"file:{quote(db_path.resolve().as_posix(), safe='/:')}?mode={mode}"

    def connect_database():
        if not allow_create:
            DatabaseLifecycle(db_path).require_available()
        return sqlite3.connect(
            database_uri,
            uri=True,
            check_same_thread=False,
        )

    engine = create_engine(
        "sqlite://",
        echo=echo,
        creator=connect_database,
        poolclass=NullPool,
    )

    @event.listens_for(engine, "connect")
    def set_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    return engine


def create_production_engine(echo: bool = False) -> Engine:
    """Create the production engine without ever materializing a missing DB."""
    db_path = get_database_path()
    state = DatabaseLifecycle(db_path).inspect()
    if state is not DatabaseLifecycleState.AVAILABLE:
        logger.warning(
            "Runtime database is not currently available: state=%s; recovery is required before first use",
            state.value,
        )
    return create_engine_for_path(db_path, echo=echo, allow_create=False)
