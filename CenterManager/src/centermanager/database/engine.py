# -*- coding: utf-8 -*-
"""
Database engine creation and management.
"""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from centermanager.core.paths import get_paths


def get_database_path() -> Path:
    """Get the path to the production database."""
    paths = get_paths()
    db_dir = paths.database_dir
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "center.db"


def create_engine_for_path(db_path: Path, echo: bool = False) -> Engine:
    """
    Create SQLAlchemy engine for SQLite with foreign key enforcement.

    Args:
        db_path: Path to SQLite database file.
        echo: Enable SQL echo for debugging.

    Returns:
        SQLAlchemy Engine instance.
    """
    db_path = Path(db_path)
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=echo,
        connect_args={
            "check_same_thread": False,
        },
    )

    # Enable foreign key enforcement
    @event.listens_for(engine, "connect")
    def set_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    return engine


def create_production_engine(echo: bool = False) -> Engine:
    """Create engine for production database."""
    return create_engine_for_path(get_database_path(), echo=echo)