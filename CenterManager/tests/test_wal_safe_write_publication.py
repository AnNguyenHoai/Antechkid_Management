# -*- coding: utf-8 -*-
"""Regression tests for WAL-safe cross-machine write publication."""

import contextlib
import shutil
import sqlite3
from types import SimpleNamespace

from centermanager.database import wal_safety
from centermanager.services import write_transaction


def test_checkpoint_flushes_committed_wal_frames_into_main_database(tmp_path, monkeypatch):
    """A committed row living in WAL must survive a center.db-only artifact copy."""
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

        # Exercise the checkpoint logic without touching the process-global test
        # runtime fence. Separate tests cover that production requests a
        # maintenance-owned handle while the fence is active.
        import centermanager.database.session as session_module

        monkeypatch.setattr(session_module, "quiesce_runtime_db", lambda: None)
        monkeypatch.setattr(session_module, "refresh_runtime_db", lambda: None)

        @contextlib.contextmanager
        def direct_connection(opener, **_kwargs):
            connection = opener()
            try:
                yield connection
            finally:
                connection.close()

        monkeypatch.setattr(wal_safety, "runtime_dbapi_connection", direct_connection)

        wal_safety.checkpoint_runtime_database_for_publish()

        artifact = tmp_path / "published-center.db"
        shutil.copy2(db_path, artifact)
        with sqlite3.connect(artifact) as published:
            values = [row[0] for row in published.execute("SELECT value FROM items ORDER BY id")]
        assert values == ["A_ONLY"]
        assert wal_path.stat().st_size == 0
    finally:
        writer.close()


def test_write_transaction_checkpoints_before_file_copy(tmp_path, monkeypatch):
    """Finish-Editing's legacy file copy cannot run before the WAL barrier."""
    runtime_root = tmp_path / "runtime"
    database_dir = runtime_root / "Database"
    repository = runtime_root / "repository"
    database_dir.mkdir(parents=True)
    repository.mkdir(parents=True)

    runtime_db = database_dir / "center.db"
    runtime_db.write_bytes(b"stale-main-file")

    monkeypatch.setattr(
        write_transaction,
        "get_paths",
        lambda: SimpleNamespace(database_dir=database_dir, runtime_root=runtime_root),
    )

    called = []

    def checkpoint_then_materialize_main_file():
        called.append("checkpoint")
        runtime_db.write_bytes(b"committed-wal-data")

    monkeypatch.setattr(
        write_transaction,
        "checkpoint_runtime_database_for_publish",
        checkpoint_then_materialize_main_file,
    )

    manager = write_transaction.WriteTransactionManager(object())
    assert manager._publish_database_and_manifest() is True
    assert called == ["checkpoint"]
    assert (repository / "database" / "center.db").read_bytes() == b"committed-wal-data"


def test_wal_barrier_is_fail_closed_and_maintenance_owned():
    source = (wal_safety.Path(wal_safety.__file__)).read_text(encoding="utf-8")
    assert "quiesce_runtime_db()" in source
    assert 'maintenance_owned=True' in source
    assert 'PRAGMA wal_checkpoint(TRUNCATE)' in source
    assert 'int(row[0]) != 0' in source
    assert "refresh_runtime_db()" in source
