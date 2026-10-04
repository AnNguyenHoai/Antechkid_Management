# -*- coding: utf-8 -*-
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

import centermanager.database.artifact_security as artifact_security
import centermanager.database.wal_safety as wal_safety
from centermanager.database.artifact_security import (
    DatabaseArtifactSecurityError,
    materialize_runtime_database_to_repository,
    validate_authoritative_repository_database,
)
from centermanager.database.encryption import apply_sqlcipher_key, load_sqlcipher_driver


KEY = b"A" * 32
SECRET = "Authoritative Sensitive Student"


class _KeyStore:
    def load(self):
        return KEY


def _paths(tmp_path):
    runtime_root = tmp_path / "runtime"
    database_dir = runtime_root / "Database"
    database_dir.mkdir(parents=True)
    return SimpleNamespace(runtime_root=runtime_root, database_dir=database_dir)


def _create_encrypted(path, value=SECRET):
    path.parent.mkdir(parents=True, exist_ok=True)
    sqlcipher = load_sqlcipher_driver()
    con = sqlcipher.connect(str(path))
    try:
        apply_sqlcipher_key(con, KEY)
        con.execute("CREATE TABLE students(name TEXT)")
        con.execute("INSERT INTO students(name) VALUES (?)", (value,))
        con.commit()
    finally:
        con.close()


def _configure(monkeypatch, paths):
    monkeypatch.setattr(artifact_security, "get_paths", lambda: paths)
    monkeypatch.setattr(artifact_security, "database_encryption_required", lambda: True)
    monkeypatch.setattr(artifact_security, "DatabaseKeyStore", _KeyStore)
    # Publication snapshotting owns its own module-level path/encryption imports.
    # Keep the security tests on the same isolated runtime instead of allowing the
    # snapshot helper to fall through to the real CI/runtime Database directory.
    monkeypatch.setattr(wal_safety, "get_paths", lambda: paths)
    monkeypatch.setattr(wal_safety, "database_encryption_required", lambda: True)
    monkeypatch.setattr(wal_safety, "DatabaseKeyStore", _KeyStore)


def test_materialize_runtime_db_keeps_authoritative_git_artifact_encrypted(tmp_path, monkeypatch):
    pytest.importorskip("sqlcipher3")
    paths = _paths(tmp_path)
    _configure(monkeypatch, paths)
    runtime_db = paths.database_dir / "center.db"
    _create_encrypted(runtime_db)

    repo_db = materialize_runtime_database_to_repository()

    raw = repo_db.read_bytes()
    assert not raw.startswith(b"SQLite format 3\x00")
    assert SECRET.encode("utf-8") not in raw
    assert validate_authoritative_repository_database() == repo_db
    assert not list(repo_db.parent.glob(".center.db.publish-*.tmp"))

    sqlcipher = load_sqlcipher_driver()
    con = sqlcipher.connect(str(repo_db))
    try:
        apply_sqlcipher_key(con, KEY)
        assert con.execute("SELECT name FROM students").fetchone()[0] == SECRET
    finally:
        con.close()


def test_materialize_refuses_plaintext_runtime_when_production_encryption_required(tmp_path, monkeypatch):
    pytest.importorskip("sqlcipher3")
    paths = _paths(tmp_path)
    _configure(monkeypatch, paths)
    runtime_db = paths.database_dir / "center.db"
    plain = sqlite3.connect(str(runtime_db))
    plain.execute("CREATE TABLE students(name TEXT)")
    plain.execute("INSERT INTO students(name) VALUES (?)", (SECRET,))
    plain.commit()
    plain.close()

    with pytest.raises(DatabaseArtifactSecurityError, match="Plaintext"):
        materialize_runtime_database_to_repository()

    assert not (paths.runtime_root / "repository" / "database" / "center.db").exists()


def test_sync_gate_refuses_plaintext_authoritative_repository_db(tmp_path, monkeypatch):
    pytest.importorskip("sqlcipher3")
    paths = _paths(tmp_path)
    _configure(monkeypatch, paths)
    repo_db = paths.runtime_root / "repository" / "database" / "center.db"
    repo_db.parent.mkdir(parents=True)
    plain = sqlite3.connect(str(repo_db))
    plain.execute("CREATE TABLE marker(value TEXT)")
    plain.commit()
    plain.close()

    with pytest.raises(DatabaseArtifactSecurityError, match="Plaintext"):
        validate_authoritative_repository_database()


def test_sync_manager_never_falls_back_to_pull_capable_publish_after_materialization():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "centermanager" / "platform" / "synchronization" / "synchronization_manager.py").read_text(encoding="utf-8")
    assert "refusing to pull after database materialization" in source
    assert "publish_call = lambda: self._provider.publish" not in source


def test_legacy_publish_workflow_never_falls_back_to_pull_capable_publish_after_materialization():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "centermanager" / "platform" / "workflow" / "publish_workflow.py").read_text(encoding="utf-8")
    assert "refusing to pull after database materialization" in source
    assert "publish_operation = self._sync_provider.publish" not in source
