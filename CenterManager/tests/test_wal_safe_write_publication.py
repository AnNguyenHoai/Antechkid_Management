# -*- coding: utf-8 -*-
"""Regression tests for WAL-safe cross-machine write publication."""

import contextlib
import sqlite3
from types import SimpleNamespace

from centermanager.database import wal_safety
from centermanager.services import write_transaction


def _install_direct_runtime_fence(monkeypatch, *, on_refresh=None):
    """Exercise WAL publication without touching the process-global test fence."""
    import centermanager.database.session as session_module

    monkeypatch.setattr(session_module, "quiesce_runtime_db", lambda: None)
    monkeypatch.setattr(
        session_module,
        "refresh_runtime_db",
        on_refresh if on_refresh is not None else (lambda: None),
    )

    @contextlib.contextmanager
    def direct_connection(opener, **_kwargs):
        connection = opener()
        try:
            yield connection
        finally:
            connection.close()

    monkeypatch.setattr(wal_safety, "runtime_dbapi_connection", direct_connection)


def test_publication_snapshot_survives_write_after_runtime_refresh(tmp_path, monkeypatch):
    """Snapshot bytes must be frozen before the maintenance fence is released."""
    database_dir = tmp_path / "Database"
    database_dir.mkdir()
    db_path = database_dir / "center.db"

    writer = sqlite3.connect(db_path)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        writer.commit()
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()

        writer.execute("INSERT INTO items(value) VALUES ('A_ONLY')")
        writer.commit()

        wal_path = db_path.with_name("center.db-wal")
        assert wal_path.exists()
        assert wal_path.stat().st_size > 0

        monkeypatch.setattr(
            wal_safety,
            "get_paths",
            lambda: SimpleNamespace(database_dir=database_dir),
        )
        monkeypatch.setattr(wal_safety, "database_encryption_required", lambda: False)

        # Simulate activity resuming immediately when the maintenance fence is
        # released. The live DB changes, but the publication snapshot must stay
        # at the exact state captured after the WAL checkpoint.
        def write_after_refresh():
            with sqlite3.connect(db_path) as resumed:
                resumed.execute("INSERT INTO items(value) VALUES ('AFTER_REFRESH')")
                resumed.commit()

        _install_direct_runtime_fence(
            monkeypatch,
            on_refresh=write_after_refresh,
        )

        with wal_safety.runtime_database_publication_snapshot() as snapshot:
            assert snapshot.exists()
            with sqlite3.connect(snapshot) as published:
                values = [
                    row[0]
                    for row in published.execute("SELECT value FROM items ORDER BY id")
                ]
            assert values == ["A_ONLY"]

            with sqlite3.connect(db_path) as live:
                live_values = [
                    row[0]
                    for row in live.execute("SELECT value FROM items ORDER BY id")
                ]
            assert live_values == ["A_ONLY", "AFTER_REFRESH"]

        assert not snapshot.exists()
    finally:
        writer.close()


def test_copy_runtime_database_for_publish_installs_snapshot_atomically(tmp_path, monkeypatch):
    database_dir = tmp_path / "Database"
    database_dir.mkdir()
    db_path = database_dir / "center.db"

    with sqlite3.connect(db_path) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        writer.execute("CREATE TABLE items (value TEXT NOT NULL)")
        writer.execute("INSERT INTO items(value) VALUES ('COMMITTED')")
        writer.commit()

    monkeypatch.setattr(
        wal_safety,
        "get_paths",
        lambda: SimpleNamespace(database_dir=database_dir),
    )
    monkeypatch.setattr(wal_safety, "database_encryption_required", lambda: False)
    _install_direct_runtime_fence(monkeypatch)

    destination = tmp_path / "repository" / "database" / "center.db"
    wal_safety.copy_runtime_database_for_publish(destination)

    with sqlite3.connect(destination) as published:
        values = [row[0] for row in published.execute("SELECT value FROM items")]
    assert values == ["COMMITTED"]
    assert not list(destination.parent.glob(".center.db.publish-copy-*.tmp"))


def test_write_transaction_uses_atomic_publication_copy(tmp_path, monkeypatch):
    """Finish Editing must not copy the live center.db directly after checkpoint."""
    runtime_root = tmp_path / "runtime"
    database_dir = runtime_root / "Database"
    repository = runtime_root / "repository"
    database_dir.mkdir(parents=True)
    repository.mkdir(parents=True)

    runtime_db = database_dir / "center.db"
    runtime_db.write_bytes(b"live-file-must-not-be-read-directly")

    monkeypatch.setattr(
        write_transaction,
        "get_paths",
        lambda: SimpleNamespace(database_dir=database_dir, runtime_root=runtime_root),
    )

    called = []

    def atomic_copy(destination):
        called.append(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"wal-complete-snapshot")
        return destination

    monkeypatch.setattr(
        write_transaction,
        "copy_runtime_database_for_publish",
        atomic_copy,
    )

    manager = write_transaction.WriteTransactionManager(object())
    assert manager._publish_database_and_manifest() is True
    expected = repository / "database" / "center.db"
    assert called == [expected]
    assert expected.read_bytes() == b"wal-complete-snapshot"


def test_wal_barrier_is_fail_closed_and_maintenance_owned():
    source = (wal_safety.Path(wal_safety.__file__)).read_text(encoding="utf-8")
    assert "quiesce_runtime_db()" in source
    assert "maintenance_owned=True" in source
    assert "PRAGMA wal_checkpoint(TRUNCATE)" in source
    assert "int(row[0]) != 0" in source
    assert "shutil.copy2(db_path, snapshot)" in source
    assert "refresh_runtime_db()" in source
    assert "os.replace(destination_tmp, destination)" in source
