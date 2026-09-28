import json
import os
import sqlite3
from types import SimpleNamespace

import centermanager.platform.backup.backup_service as backup_module
from centermanager.platform.backup.backup_service import BackupService
from centermanager.platform.backup.restore_authorization import issue_restore_authorization


def _write_db(path, value):
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker(value) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def _read_marker(path):
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return connection.execute("SELECT value FROM marker").fetchone()[0]
    finally:
        connection.close()


def _authorization(reason="rollback test"):
    actor = SimpleNamespace(id=1, username="admin", is_admin=True)
    return issue_restore_authorization(
        actor=actor,
        reason=reason,
        confirmation="RESTORE snapshot",
    )


def _runtime_fixture(tmp_path, monkeypatch):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    snapshot = backup_root / "snapshot"
    snapshot.mkdir()
    snapshot_meta = snapshot / "metadata"
    snapshot_meta.mkdir()
    (snapshot_meta / "state.txt").write_text("new", encoding="utf-8")
    _write_db(snapshot / "center.db", "new")
    (snapshot / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": BackupService.FORMAT_VERSION,
                "database": "center.db",
                "database_encrypted": False,
                "metadata": "metadata",
                "checksums": {},
            }
        ),
        encoding="utf-8",
    )

    database_dir = tmp_path / "database"
    database_dir.mkdir()
    runtime_db = database_dir / "center.db"
    _write_db(runtime_db, "old")

    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "state.txt").write_text("old", encoding="utf-8")

    paths = SimpleNamespace(
        backup_dir=tmp_path,
        database_dir=database_dir,
        metadata_dir=metadata_dir,
    )
    monkeypatch.setattr(backup_module, "get_paths", lambda: paths)
    monkeypatch.setattr(backup_module, "refresh_runtime_db", lambda: None)

    service = BackupService.__new__(BackupService)
    service._backup_root = backup_root.resolve()
    service._event_bus = None
    monkeypatch.setattr(service, "_encryption_context", lambda: (False, None))
    return service, snapshot, database_dir, runtime_db, metadata_dir


def test_metadata_swap_failure_rolls_database_and_metadata_back(tmp_path, monkeypatch):
    service, snapshot, _, runtime_db, metadata_dir = _runtime_fixture(tmp_path, monkeypatch)
    real_replace = os.replace

    def fail_metadata_install(src, dst):
        src_path = backup_module.Path(src)
        dst_path = backup_module.Path(dst)
        if src_path.name.startswith(".metadata.restore-") and dst_path == metadata_dir:
            raise OSError("injected metadata swap failure")
        return real_replace(src, dst)

    monkeypatch.setattr(backup_module.os, "replace", fail_metadata_install)

    result = service.restore_backup(snapshot, authorization=_authorization())

    assert result.success is False
    assert "metadata swap failure" in result.error
    assert _read_marker(runtime_db) == "old"
    assert (metadata_dir / "state.txt").read_text(encoding="utf-8") == "old"


def test_live_metadata_preserve_failure_restores_db_metadata_and_sidecars(tmp_path, monkeypatch):
    service, snapshot, database_dir, runtime_db, metadata_dir = _runtime_fixture(tmp_path, monkeypatch)
    # Capture the closed, checkpointed database before creating synthetic
    # sidecars.  The sidecars below are sentinel bytes, not valid SQLite WAL/SHM
    # files, so reopening SQLite while they are present is intentionally avoided.
    old_db_bytes = runtime_db.read_bytes()
    wal = backup_module.Path(str(runtime_db) + "-wal")
    shm = backup_module.Path(str(runtime_db) + "-shm")
    wal.write_bytes(b"old-wal")
    shm.write_bytes(b"old-shm")
    real_replace = os.replace

    def fail_live_metadata_preserve(src, dst):
        src_path = backup_module.Path(src)
        dst_path = backup_module.Path(dst)
        if src_path == metadata_dir and dst_path.name.startswith(".metadata.previous-"):
            raise OSError("injected metadata preserve failure")
        return real_replace(src, dst)

    monkeypatch.setattr(backup_module.os, "replace", fail_live_metadata_preserve)

    result = service.restore_backup(
        snapshot,
        authorization=_authorization("preservation rollback test"),
    )

    assert result.success is False
    assert "metadata preserve failure" in result.error
    assert runtime_db.read_bytes() == old_db_bytes
    assert (metadata_dir / "state.txt").read_text(encoding="utf-8") == "old"
    assert wal.read_bytes() == b"old-wal"
    assert shm.read_bytes() == b"old-shm"
    assert not list(database_dir.glob(".center.db.previous-*"))
    assert not list(database_dir.glob(".center.db-wal.previous-*"))
    assert not list(database_dir.glob(".center.db-shm.previous-*"))
    assert not list(tmp_path.glob(".metadata.previous-*"))
