"""Prove real CLEAN fingerprints do not include protected handoff backups.

This test is distinct from mocked handoff materialization tests: it uses the
actual WriteRecoveryJournal file-hashing and fail-closed acceptance guard.
"""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.write_recovery import RecoveryRequired, WriteRecoveryJournal


def _journal(tmp_path):
    runtime = tmp_path / "runtime"
    repo = runtime / "repository"
    (repo / ".git").mkdir(parents=True)
    (repo / "database").mkdir()
    database = runtime / "Database" / "center.db"
    database.parent.mkdir()
    database.write_bytes(b"accepted-authoritative-main-after-migration")
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()

    j = WriteRecoveryJournal.__new__(WriteRecoveryJournal)
    j.runtime = runtime
    j.repository = repo
    j.database = database
    j.root = root
    j.journal = root / "journal.json"
    j.paths = SimpleNamespace(
        metadata_dir=runtime / "metadata",
        attachment_dir=runtime / "Attachment",
        export_dir=runtime / "Export",
        reports_dir=runtime / "Reports",
    )
    receipt = {
        "status": "CLEAN",
        "publication": "VERIFIED",
        "repository_id": "test-repository",
        "published_oid": "main",
        "published_runtime_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "accepted_local_files": j._local_files(),
    }
    j.inspect = lambda: receipt
    j._repository_id = lambda: "test-repository"
    j._wal_pending = lambda: False
    j._git = lambda *args: {
        ("rev-parse", "HEAD"): "main",
        ("rev-parse", "@{upstream}"): "main",
        ("status", "--porcelain", "--untracked-files=all"): "",
    }[args]
    return j, receipt


def test_rollback_directory_can_be_deleted_without_invalidating_receipt(tmp_path):
    j, receipt = _journal(tmp_path)
    rollback_dir = j.root / "handoff-rollback" / "session-token"
    rollback_dir.mkdir(parents=True)
    (rollback_dir / ".center.db.previous-session-token").write_bytes(b"old-db")
    (rollback_dir / ".center.db-wal.previous-session-token").write_bytes(b"old-wal")

    assert j._local_files() == receipt["accepted_local_files"]
    j.assert_replaceable()

    for child in rollback_dir.iterdir():
        child.unlink()
    rollback_dir.rmdir()

    assert j._local_files() == receipt["accepted_local_files"]
    j.assert_replaceable()


def test_undeclared_backup_inside_business_database_still_fails_closed(tmp_path):
    j, _ = _journal(tmp_path)
    (j.database.parent / ".center.db.previous-unexpected").write_bytes(b"old-db")

    with pytest.raises(RecoveryRequired):
        j.assert_replaceable()


def test_other_database_files_remain_protected_by_clean_receipt(tmp_path):
    j, _ = _journal(tmp_path)
    (j.database.parent / "other-user-data.sqlite").write_bytes(b"business-data")

    with pytest.raises(RecoveryRequired):
        j.assert_replaceable()
