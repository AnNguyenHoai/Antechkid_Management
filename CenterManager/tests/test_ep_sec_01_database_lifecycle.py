from pathlib import Path
import sqlite3

import pytest

from centermanager.database.lifecycle import (
    DatabaseLifecycle,
    DatabaseLifecycleError,
    DatabaseLifecycleState,
)
from centermanager.database.engine import create_engine_for_path


def test_missing_database_is_recovery_required_and_never_created(tmp_path: Path):
    db_path = tmp_path / "center.db"
    lifecycle = DatabaseLifecycle(db_path)

    assert lifecycle.inspect() is DatabaseLifecycleState.MISSING
    assert lifecycle.state_or_recovery() is DatabaseLifecycleState.RECOVERY_REQUIRED
    with pytest.raises(DatabaseLifecycleError):
        lifecycle.require_available()

    engine = create_engine_for_path(db_path)
    with pytest.raises(DatabaseLifecycleError):
        with engine.connect():
            pass
    engine.dispose()

    assert not db_path.exists()


def test_empty_file_is_corrupted(tmp_path: Path):
    db_path = tmp_path / "center.db"
    db_path.touch()
    assert DatabaseLifecycle(db_path).inspect() is DatabaseLifecycleState.CORRUPTED


def test_empty_sqlite_database_is_invalid_schema(tmp_path: Path):
    db_path = tmp_path / "center.db"
    connection = sqlite3.connect(db_path)
    connection.close()

    assert DatabaseLifecycle(db_path).inspect() is DatabaseLifecycleState.INVALID_SCHEMA
    with pytest.raises(DatabaseLifecycleError):
        DatabaseLifecycle(db_path).require_available()


def test_valid_sqlite_database_is_available(tmp_path: Path):
    db_path = tmp_path / "center.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE students (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()

    lifecycle = DatabaseLifecycle(db_path)
    assert lifecycle.inspect() is DatabaseLifecycleState.AVAILABLE
    lifecycle.require_available()

    engine = create_engine_for_path(db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
    finally:
        engine.dispose()


def test_corrupt_database_is_recovery_required(tmp_path: Path):
    db_path = tmp_path / "center.db"
    db_path.write_bytes(b"not-a-sqlite-database")

    lifecycle = DatabaseLifecycle(db_path)
    assert lifecycle.inspect() is DatabaseLifecycleState.CORRUPTED
    assert lifecycle.state_or_recovery() is DatabaseLifecycleState.RECOVERY_REQUIRED
    with pytest.raises(DatabaseLifecycleError):
        lifecycle.require_available()
