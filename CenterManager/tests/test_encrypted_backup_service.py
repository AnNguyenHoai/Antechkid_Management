# -*- coding: utf-8 -*-
from types import SimpleNamespace
import sqlite3

import pytest

import centermanager.platform.backup.backup_service as backup_module
from centermanager.database.encryption import apply_sqlcipher_key, load_sqlcipher_driver
from centermanager.platform.backup.backup_service import BackupService
from centermanager.platform.backup.restore_authorization import issue_restore_authorization


KEY = bytes(range(32))
SENSITIVE_VALUE = "Sensitive Student Backup Value"


class _KeyStore:
    def load(self) -> bytes:
        return KEY


def _paths(tmp_path):
    runtime = tmp_path / "runtime"
    database_dir = runtime / "Database"
    metadata_dir = runtime / "metadata"
    backup_dir = runtime / "Backups"
    database_dir.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    backup_dir.mkdir(parents=True)
    (metadata_dir / "version.json").write_text('{"platform_version": 1}', encoding="utf-8")
    return SimpleNamespace(
        database_dir=database_dir,
        metadata_dir=metadata_dir,
        backup_dir=backup_dir,
    )


def _create_encrypted_database(path, value=SENSITIVE_VALUE):
    sqlcipher = load_sqlcipher_driver()
    connection = sqlcipher.connect(str(path))
    try:
        apply_sqlcipher_key(connection, KEY)
        connection.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        connection.execute("INSERT INTO students(name) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def _read_encrypted_value(path):
    sqlcipher = load_sqlcipher_driver()
    connection = sqlcipher.connect(str(path))
    try:
        apply_sqlcipher_key(connection, KEY)
        return connection.execute("SELECT name FROM students").fetchone()[0]
    finally:
        connection.close()


def _configure_encrypted_runtime(monkeypatch, paths):
    monkeypatch.setattr(backup_module, "get_paths", lambda: paths)
    monkeypatch.setattr(backup_module, "database_encryption_required", lambda: True)
    monkeypatch.setattr(backup_module, "DatabaseKeyStore", _KeyStore)
    monkeypatch.setattr(backup_module, "refresh_runtime_db", lambda: None)


def _restore_authorization(backup_path):
    actor = SimpleNamespace(id=1, username="test-admin", is_admin=True)
    return issue_restore_authorization(
        actor=actor,
        reason="encrypted backup restore test",
        confirmation=f"RESTORE {backup_path.name}",
    )


def test_production_backup_is_ciphertext_and_restores_without_plaintext_temp(tmp_path, monkeypatch):
    pytest.importorskip("sqlcipher3")
    paths = _paths(tmp_path)
    _configure_encrypted_runtime(monkeypatch, paths)
    runtime_db = paths.database_dir / "center.db"
    _create_encrypted_database(runtime_db)

    service = BackupService()
    result = service.create_backup("security")

    assert result.success, result.error
    backup_db = result.backup_path / "center.db"
    raw = backup_db.read_bytes()
    assert not raw.startswith(b"SQLite format 3\x00")
    assert SENSITIVE_VALUE.encode("utf-8") not in raw

    with pytest.raises(sqlite3.DatabaseError):
        plain = sqlite3.connect(str(backup_db))
        try:
            plain.execute("SELECT name FROM students").fetchall()
        finally:
            plain.close()

    assert _read_encrypted_value(backup_db) == SENSITIVE_VALUE

    # Replace runtime content, then restore the encrypted snapshot.
    runtime_db.unlink()
    _create_encrypted_database(runtime_db, "Changed after backup")
    restored = service.restore_backup(
        result.backup_path,
        authorization=_restore_authorization(result.backup_path),
    )
    assert restored.success, restored.error
    assert _read_encrypted_value(runtime_db) == SENSITIVE_VALUE

    raw_runtime = runtime_db.read_bytes()
    assert not raw_runtime.startswith(b"SQLite format 3\x00")
    assert SENSITIVE_VALUE.encode("utf-8") not in raw_runtime
    assert not list(paths.database_dir.glob(".center.db.restore-*.tmp"))


def test_production_backup_refuses_plaintext_runtime_database(tmp_path, monkeypatch):
    pytest.importorskip("sqlcipher3")
    paths = _paths(tmp_path)
    _configure_encrypted_runtime(monkeypatch, paths)
    runtime_db = paths.database_dir / "center.db"

    plain = sqlite3.connect(str(runtime_db))
    try:
        plain.execute("CREATE TABLE students (name TEXT)")
        plain.execute("INSERT INTO students(name) VALUES (?)", (SENSITIVE_VALUE,))
        plain.commit()
    finally:
        plain.close()

    service = BackupService()
    result = service.create_backup("security")

    assert not result.success
    assert "plaintext" in (result.error or "").lower()
    assert not list((paths.backup_dir / "publish").glob("security_*"))


def test_production_restore_refuses_manifest_marked_plaintext(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    _configure_encrypted_runtime(monkeypatch, paths)
    service = BackupService()

    backup = paths.backup_dir / "publish" / "legacy"
    backup.mkdir(parents=True)
    (backup / "metadata").mkdir()
    plain = sqlite3.connect(str(backup / "center.db"))
    plain.execute("CREATE TABLE marker(value TEXT)")
    plain.commit()
    plain.close()
    (backup / "manifest.json").write_text(
        '{"format_version":2,"database":"center.db","metadata":"metadata","database_encrypted":false}',
        encoding="utf-8",
    )

    result = service.restore_backup(
        backup,
        authorization=_restore_authorization(backup),
    )
    assert not result.success
    assert "plaintext" in (result.error or "").lower() or "legacy" in (result.error or "").lower()
