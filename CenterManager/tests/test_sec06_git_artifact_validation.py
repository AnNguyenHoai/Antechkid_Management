# -*- coding: utf-8 -*-
"""Regression: authoritative SQLCipher/SQLite inspections must never dirty Git.

The in-repository DB is a standalone, signed snapshot; existing WAL state
requires explicit review and must not be silently ignored as immutable.
"""
from pathlib import Path
from contextlib import contextmanager
import sqlite3

import pytest

from centermanager.database.artifact_security import (
    DatabaseArtifactSecurityError,
    validate_database_artifact,
)


def _sidecars(path: Path):
    return tuple(path.with_name(path.name + suffix)
                 for suffix in ("-wal", "-shm", "-journal"))


def test_plain_artifact_validation_does_not_create_git_wal_or_shm(tmp_path):
    repo = tmp_path / "repository" / "database"
    repo.mkdir(parents=True)
    db = repo / "center.db"
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO fixture VALUES (1)")
        connection.commit()
    finally:
        connection.close()
    assert all(not p.exists() for p in _sidecars(db))
    validate_database_artifact(db, encryption_required=False)
    assert all(not p.exists() for p in _sidecars(db))
    # Explicitly close readers; sqlite3 context manager only commits/rolls back.
    connection = sqlite3.connect(db)
    try:
        assert connection.execute("SELECT count(*) FROM fixture").fetchone() == (1,)
    finally:
        connection.close()


def test_standalone_artifact_refuses_existing_uncommitted_sidecars(tmp_path):
    db = tmp_path / "center.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE fixture (id INTEGER)")
    wal = db.with_name(db.name + "-wal")
    wal.write_bytes(b"untrusted WAL evidence")
    with pytest.raises(DatabaseArtifactSecurityError, match="sidecar"):
        validate_database_artifact(db, encryption_required=False)
    assert wal.read_bytes() == b"untrusted WAL evidence"


def test_live_runtime_validation_does_not_assume_immutable_snapshot(tmp_path, monkeypatch):
    """Exercise the live-path URI without inheriting a global maintenance fence.

    A separate lifecycle suite validates runtime handle registration. This test
    verifies that runtime_guarded retains WAL visibility rather than using an
    immutable snapshot, while isolating the unrelated global connection gate.
    """
    import centermanager.database.artifact_security as artifact_module

    db = tmp_path / "center.db"
    writer = sqlite3.connect(db)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE fixture (id INTEGER)")
        writer.commit()
        assert artifact_module._artifact_read_uri(
            db, runtime_guarded=True
        ).endswith("?mode=ro")

        @contextmanager
        def isolated_runtime_reader(opener, *, owner):
            connection = opener()
            try:
                yield connection
            finally:
                connection.close()

        monkeypatch.setattr(
            artifact_module, "runtime_dbapi_connection", isolated_runtime_reader
        )
        validate_database_artifact(
            db, encryption_required=False, runtime_guarded=True
        )
    finally:
        writer.close()


def test_sqlcipher_artifact_validation_does_not_create_git_sidecars(tmp_path):
    from centermanager.database.encryption import (
        load_sqlcipher_driver, apply_sqlcipher_key,
    )
    try:
        sqlcipher = load_sqlcipher_driver()
    except Exception:
        pytest.skip("SQLCipher native driver is unavailable")
    db = tmp_path / "repository" / "database" / "center.db"
    db.parent.mkdir(parents=True)
    key = b"Q" * 32
    connection = sqlcipher.connect(str(db))
    try:
        apply_sqlcipher_key(connection, key)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE fixture (id INTEGER)")
        connection.execute("INSERT INTO fixture VALUES (2)")
        connection.commit()
    finally:
        connection.close()
    assert all(not p.exists() for p in _sidecars(db))
    validate_database_artifact(db, encryption_required=True, key=key)
    assert all(not p.exists() for p in _sidecars(db))
