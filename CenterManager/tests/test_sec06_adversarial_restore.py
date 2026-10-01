# -*- coding: utf-8 -*-
"""SEC-06 adversarial restore contracts.

These tests intentionally exercise the fail-closed boundary before destructive
runtime mutation. They complement the Windows happy-path restore UAT.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.backup.backup_service import BackupService
from centermanager.platform.backup.restore_authorization import (
    RestoreAuthorization,
    issue_restore_authorization,
    validate_restore_authorization,
)


def _service(tmp_path: Path) -> BackupService:
    service = BackupService.__new__(BackupService)
    service._backup_root = (tmp_path / "backups").resolve()
    service._backup_root.mkdir(parents=True, exist_ok=True)
    service._event_bus = None
    return service


def _managed_backup(service: BackupService, *, db_bytes: bytes = b"encrypted-db") -> Path:
    backup = service._backup_root / "candidate"
    backup.mkdir()
    db = backup / "center.db"
    db.write_bytes(db_bytes)
    (backup / "metadata").mkdir()
    manifest = {
        "format_version": service.FORMAT_VERSION,
        "database": "center.db",
        "database_encrypted": True,
        "metadata": "metadata",
        "checksums": {"center.db": hashlib.sha256(db_bytes).hexdigest()},
    }
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return backup


def _admin():
    return SimpleNamespace(id="admin-1", username="security-admin", is_admin=True)


def _authorization():
    return issue_restore_authorization(
        actor=_admin(), reason="SEC-06 adversarial UAT", confirmation="RESTORE"
    )


def test_direct_platform_restore_without_authority_fails_before_backup_validation(tmp_path, monkeypatch):
    service = _service(tmp_path)
    touched = False

    def forbidden_validation(_path):
        nonlocal touched
        touched = True
        raise AssertionError("validation must not run before authorization")

    monkeypatch.setattr(service, "_validate_backup", forbidden_validation)

    result = service.restore_backup(service._backup_root / "anything", authorization=None)

    assert result.success is False
    assert "authorization" in (result.error or "").lower()
    assert touched is False


def test_restore_authorization_cannot_be_forged_by_constructing_dataclass():
    forged = RestoreAuthorization(
        actor_id="attacker",
        actor_name="attacker",
        reason="bypass",
        confirmation="RESTORE",
        _authority=object(),
    )

    with pytest.raises(PermissionError):
        validate_restore_authorization(forged)


def test_non_admin_cannot_issue_restore_authority():
    actor = SimpleNamespace(id="user-1", username="user", is_admin=False)

    with pytest.raises(PermissionError):
        issue_restore_authorization(actor=actor, reason="test", confirmation="RESTORE")


def test_empty_reason_or_confirmation_cannot_issue_restore_authority():
    with pytest.raises(ValueError):
        issue_restore_authorization(actor=_admin(), reason="", confirmation="RESTORE")
    with pytest.raises(ValueError):
        issue_restore_authorization(actor=_admin(), reason="test", confirmation="")


def test_backup_outside_managed_root_is_rejected_before_database_validation(tmp_path, monkeypatch):
    service = _service(tmp_path)
    outside = tmp_path / "attacker-backup"
    outside.mkdir()
    (outside / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        service,
        "_validate_database",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("outside backup must not reach DB validation")
        ),
    )

    ok, error = service._validate_backup(outside)

    assert ok is False
    assert "outside" in error.lower()


def test_tampered_backup_checksum_is_rejected(tmp_path, monkeypatch):
    service = _service(tmp_path)
    backup = _managed_backup(service, db_bytes=b"original-encrypted-pages")
    db = backup / "center.db"
    # Simulate an attacker modifying the encrypted artifact after the manifest was issued.
    db.write_bytes(b"tampered-encrypted-pages")

    monkeypatch.setattr(service, "_encryption_context", lambda: (True, b"k" * 32))
    # Isolate checksum contract from SQLCipher availability in unit CI. Integrity/key
    # behavior is covered separately below and by the Windows packaged-app UAT.
    monkeypatch.setattr(service, "_validate_database", lambda *args, **kwargs: None)

    ok, error = service._validate_backup(backup)

    assert ok is False
    assert "checksum mismatch" in error.lower()


def test_wrong_workspace_key_or_invalid_ciphertext_is_rejected(tmp_path, monkeypatch):
    service = _service(tmp_path)
    backup = _managed_backup(service)
    monkeypatch.setattr(service, "_encryption_context", lambda: (True, b"wrong-key"))
    monkeypatch.setattr(
        service,
        "_validate_database",
        lambda *args, **kwargs: "Invalid encrypted database or wrong workspace key: file is not a database",
    )

    ok, error = service._validate_backup(backup)

    assert ok is False
    assert "wrong workspace key" in error.lower()


def test_plaintext_or_legacy_backup_is_rejected_when_encryption_is_required(tmp_path, monkeypatch):
    service = _service(tmp_path)
    backup = _managed_backup(service)
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database_encrypted"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(service, "_encryption_context", lambda: (True, b"k" * 32))

    ok, error = service._validate_backup(backup)

    assert ok is False
    assert "plaintext" in error.lower() or "legacy" in error.lower()


def test_missing_metadata_is_rejected(tmp_path, monkeypatch):
    service = _service(tmp_path)
    backup = _managed_backup(service)
    (backup / "metadata").rmdir()
    monkeypatch.setattr(service, "_encryption_context", lambda: (True, b"k" * 32))
    monkeypatch.setattr(service, "_validate_database", lambda *args, **kwargs: None)

    ok, error = service._validate_backup(backup)

    assert ok is False
    assert "metadata" in error.lower()


def test_future_backup_format_is_rejected_fail_closed(tmp_path):
    service = _service(tmp_path)
    backup = _managed_backup(service)
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["format_version"] = service.FORMAT_VERSION + 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    ok, error = service._validate_backup(backup)

    assert ok is False
    assert "newer" in error.lower()
