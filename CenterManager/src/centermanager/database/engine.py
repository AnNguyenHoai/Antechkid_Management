# -*- coding: utf-8 -*-
import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from centermanager.core.paths import get_paths

logger = logging.getLogger(__name__)

def get_database_path() -> Path:
    paths = get_paths()
    db_dir = paths.database_dir
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "center.db"

def create_engine_for_path(db_path: Path, echo: bool = False) -> Engine:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Sử dụng SQLite thuần, không mã hóa
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=echo,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )

    @event.listens_for(engine, "connect")
    def set_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    return engine

def create_production_engine(echo: bool = False) -> Engine:
    db_path = get_database_path()
    if not db_path.exists():
        logger.info("Database file not found. A new database will be created.")
    return create_engine_for_path(db_path, echo=echo)