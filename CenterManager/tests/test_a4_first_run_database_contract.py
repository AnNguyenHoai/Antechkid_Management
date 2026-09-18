# -*- coding: utf-8 -*-
"""A4.1 first-run database lifecycle contract tests."""

import sqlite3
from pathlib import Path

from centermanager.database.engine import initialize_runtime_database


def test_initialize_runtime_database_creates_missing_file(tmp_path):
    db_path = tmp_path / "runtime" / "Database" / "center.db"

    # Patch the path accessor used by the lifecycle helper.
    import centermanager.database.engine as engine_module
    original = engine_module.get_database_path
    engine_module.get_database_path = lambda: db_path
    try:
        result = initialize_runtime_database()
    finally:
        engine_module.get_database_path = original

    assert result == db_path
    assert db_path.is_file()
    assert sqlite3.connect(db_path).execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_initialize_runtime_database_never_overwrites_existing_database(tmp_path):
    db_path = tmp_path / "center.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE sentinel (value TEXT)")
    connection.execute("INSERT INTO sentinel VALUES ('keep')")
    connection.commit()
    connection.close()

    import centermanager.database.engine as engine_module
    original = engine_module.get_database_path
    engine_module.get_database_path = lambda: db_path
    try:
        initialize_runtime_database()
    finally:
        engine_module.get_database_path = original

    connection = sqlite3.connect(db_path)
    assert connection.execute("SELECT value FROM sentinel").fetchone()[0] == "keep"
    connection.close()


def test_app_explicitly_initializes_database_before_engine():
    source = (
        Path(__file__).resolve().parents[1] / "src/centermanager/app.py"
    ).read_text(encoding="utf-8")
    assert "initialize_runtime_database()" in source
