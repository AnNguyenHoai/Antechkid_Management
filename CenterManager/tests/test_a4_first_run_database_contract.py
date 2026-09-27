# -*- coding: utf-8 -*-
"""A4.1 first-run database lifecycle contract tests."""

import sqlite3
from pathlib import Path

from centermanager.database.engine import initialize_runtime_database
from centermanager.database.encryption import (
    apply_sqlcipher_key,
    database_encryption_required,
    is_plaintext_sqlite_file,
    load_sqlcipher_driver,
)


def test_initialize_runtime_database_creates_missing_file(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime" / "Database" / "center.db"
    test_key = b"A" * 32

    # Patch the path accessor used by the lifecycle helper. Encrypted Windows
    # first-run also receives deterministic key material so the contract does
    # not depend on the CI runner's DPAPI profile.
    import centermanager.database.engine as engine_module

    class _TestKeyStore:
        def load_or_create(self, *, allow_create: bool):
            assert allow_create is True
            return test_key

    monkeypatch.setattr(engine_module, "get_database_path", lambda: db_path)
    if database_encryption_required():
        monkeypatch.setattr(engine_module, "DatabaseKeyStore", _TestKeyStore)

    result = initialize_runtime_database()

    assert result == db_path
    assert db_path.is_file()

    if database_encryption_required():
        assert not is_plaintext_sqlite_file(db_path)
        sqlcipher = load_sqlcipher_driver()
        connection = sqlcipher.connect(str(db_path))
        try:
            apply_sqlcipher_key(connection, test_key)
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()
    else:
        connection = sqlite3.connect(db_path)
        try:
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()


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
