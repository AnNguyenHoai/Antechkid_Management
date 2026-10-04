# -*- coding: utf-8 -*-
"""Regression coverage for Git -> waiting-writer runtime materialization."""

import sqlite3
from types import SimpleNamespace

import centermanager.platform.sync.write_handoff_runtime_sync_service as hardened_sync


def _make_plain_db(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE items(value TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO items(value) VALUES (?)",
            [(value,) for value in values],
        )
        connection.commit()
    finally:
        connection.close()


def _read_values(path):
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute("SELECT value FROM items ORDER BY rowid")]
    finally:
        connection.close()


def _paths(tmp_path):
    runtime_root = tmp_path / "runtime"
    database_dir = runtime_root / "Database"
    metadata_dir = runtime_root / "metadata"
    database_dir.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    return SimpleNamespace(
        runtime_root=runtime_root,
        database_dir=database_dir,
        metadata_dir=metadata_dir,
    )


def _service(monkeypatch, paths, writer=None):
    service = object.__new__(hardened_sync.RuntimeSyncService)
    fence = {"active": False}
    order = []

    monkeypatch.setattr(hardened_sync, "get_paths", lambda: paths)
    monkeypatch.setattr(hardened_sync, "database_encryption_required", lambda: False)
    monkeypatch.setattr(
        hardened_sync,
        "validate_authoritative_repository_database",
        lambda: paths.runtime_root / "repository" / "database" / "center.db",
    )

    import centermanager.database.session as session_module

    def quiesce():
        order.append("quiesce")
        fence["active"] = True
        if writer is not None:
            writer.close()

    monkeypatch.setattr(session_module, "quiesce_runtime_db", quiesce)
    monkeypatch.setattr(
        session_module,
        "runtime_db_maintenance_active",
        lambda: fence["active"],
    )

    def refresh():
        order.append("refresh")
        fence["active"] = False

    service._refresh_db_sessions = refresh
    return service, fence, order


def test_waiting_writer_discards_stale_local_wal_and_uses_git_authority(tmp_path, monkeypatch):
    """A's Git DB must replace B's DB+WAL before B can enter WRITE."""
    paths = _paths(tmp_path)
    repo_db = paths.runtime_root / "repository" / "database" / "center.db"
    _make_plain_db(repo_db, ["BASE", "A_ONLY"])

    repo_manifest = paths.runtime_root / "repository" / "manifest.json"
    repo_manifest.parent.mkdir(parents=True, exist_ok=True)
    repo_manifest.write_text('{"runtime_version": 42}\n', encoding="utf-8")

    runtime_db = paths.database_dir / "center.db"
    writer = sqlite3.connect(runtime_db)
    assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("CREATE TABLE items(value TEXT NOT NULL)")
    writer.execute("INSERT INTO items(value) VALUES ('BASE')")
    writer.commit()
    writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    writer.execute("INSERT INTO items(value) VALUES ('B_STALE')")
    writer.commit()

    wal = runtime_db.with_name("center.db-wal")
    assert wal.exists()
    assert wal.stat().st_size > 0

    service, fence, order = _service(monkeypatch, paths, writer=writer)

    assert service._apply_runtime_update() is True
    assert order[0] == "quiesce"
    assert "refresh" in order
    assert fence["active"] is False
    assert _read_values(runtime_db) == ["BASE", "A_ONLY"]
    assert not runtime_db.with_name("center.db-wal").exists()
    assert not runtime_db.with_name("center.db-shm").exists()
    assert (paths.runtime_root / "manifest.json").read_text(encoding="utf-8") == repo_manifest.read_text(encoding="utf-8")


def test_live_runtime_is_not_replaced_before_quiesce(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    repo_db = paths.runtime_root / "repository" / "database" / "center.db"
    _make_plain_db(repo_db, ["LATEST"])

    runtime_db = paths.database_dir / "center.db"
    _make_plain_db(runtime_db, ["OLD"])

    service, fence, order = _service(monkeypatch, paths)
    real_replace = hardened_sync.os.replace

    def guarded_replace(source, destination):
        destination = hardened_sync.Path(destination)
        if destination == runtime_db or destination.name.startswith(".center.db.previous-"):
            assert fence["active"], "live runtime DB mutated before maintenance quiesce"
            order.append("runtime-mutation")
        return real_replace(source, destination)

    monkeypatch.setattr(hardened_sync.os, "replace", guarded_replace)

    assert service._apply_runtime_update() is True
    assert order.index("quiesce") < order.index("runtime-mutation") < order.index("refresh")
    assert _read_values(runtime_db) == ["LATEST"]


def test_refresh_failure_rolls_back_and_rejects_handoff(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    repo_db = paths.runtime_root / "repository" / "database" / "center.db"
    _make_plain_db(repo_db, ["A_ONLY"])

    runtime_db = paths.database_dir / "center.db"
    _make_plain_db(runtime_db, ["OLD_B"])

    service, fence, order = _service(monkeypatch, paths)
    refresh_calls = {"count": 0}

    def refresh_with_first_failure():
        refresh_calls["count"] += 1
        order.append("refresh")
        if refresh_calls["count"] == 1:
            # Mirror refresh_runtime_db(): a failed rebuild re-enters maintenance.
            fence["active"] = True
            raise RuntimeError("session refresh failed")
        fence["active"] = False

    service._refresh_db_sessions = refresh_with_first_failure

    assert service._apply_runtime_update() is False
    assert refresh_calls["count"] == 2
    assert fence["active"] is False
    assert _read_values(runtime_db) == ["OLD_B"]
