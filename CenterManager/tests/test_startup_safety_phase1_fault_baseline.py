"""Phase 1 baseline/fault-injection characterization; disposable paths ONLY.

These tests intentionally capture the existing risky behaviour before the
narrow remediations. No production Git or SQLCipher database is opened.
Requirements SYS-006, COL-001..012; WF-01, WF-04, WF-05 and WF-28.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest
import centermanager.platform.sync.startup_sync as startup_module
from centermanager.platform.sync.startup_sync import StartupSynchronization
from centermanager.platform.sync.startup_install_replay import (
    capture_before_install, InterruptedInstallError,
)


def test_locked_obsolete_cleanup_is_advisory_after_acceptance(monkeypatch, tmp_path):
    """Once accepted, cleanup cannot veto MAIN or erase previous evidence."""
    artifact = tmp_path / "old-employee-backup"
    artifact.mkdir()
    (artifact / "old.txt").write_text("prior evidence")
    sync = StartupSynchronization.__new__(StartupSynchronization)
    sync._startup_assets = ([(tmp_path / "Employees", artifact, True)], None)
    sync._review_only_reset_requested = False
    def locked(_path):
        raise PermissionError("simulated Windows locked backup")
    monkeypatch.setattr(startup_module.shutil, "rmtree", locked)
    sync._finalize_startup_assets()
    assert artifact.exists()
    assert sync._startup_assets is None


def test_locked_old_database_backup_never_blocks_after_verified_install(
    monkeypatch, tmp_path,
):
    db = tmp_path / "Database" / "center.db"
    db.parent.mkdir()
    db.write_bytes(b"verified-main")
    obsolete = tmp_path / "previous-old.db"
    obsolete.write_bytes(b"older-data")
    sync = StartupSynchronization.__new__(StartupSynchronization)
    sync._startup_db_install_backup = (db, obsolete, True, ())
    original_unlink = Path.unlink
    def locked_unlink(path, *args, **kwargs):
        if path == obsolete:
            raise PermissionError("Windows file lock")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", locked_unlink)
    sync._finalize_startup_database_install()
    assert db.read_bytes() == b"verified-main"
    assert obsolete.read_bytes() == b"older-data"
    assert sync._startup_db_install_backup is None


def test_review_mode_preserves_old_employee_archive_without_recursing(tmp_path):
    archive = tmp_path / "very-long-existing-archive"
    archive.mkdir()
    (archive / "evidence.txt").write_text("old unsent data")
    sync = StartupSynchronization.__new__(StartupSynchronization)
    sync._startup_assets = ([(tmp_path / "Employees", archive, True)], None)
    sync._review_only_reset_requested = True
    sync._finalize_startup_assets()
    assert (archive / "evidence.txt").read_text() == "old unsent data"
    assert sync._startup_assets is None


def test_crash_snapshot_copy_failure_keeps_original_and_no_acceptance_marker(
    monkeypatch, tmp_path,
):
    root = tmp_path / "runtime"
    old_db = root / "Database" / "center.db"
    old_db.parent.mkdir(parents=True)
    old_db.write_bytes(b"opaque-old-sqlcipher-evidence")
    old_attachment = root / "Attachments" / "Employees" / "viet-name"
    old_attachment.mkdir(parents=True)
    (old_attachment / "receipt.pdf").write_bytes(b"original-employee-pdf")
    marker = tmp_path / "runtime.write-recovery" / "startup-install.pending.json"
    from centermanager.platform.sync import startup_install_replay as replay
    original = replay._copy_and_sync
    def fails_on_attachment(src, dest):
        if src.name == "receipt.pdf":
            raise OSError(206, "simulated Windows path too long")
        return original(src, dest)
    monkeypatch.setattr(replay, "_copy_and_sync", fails_on_attachment)
    with pytest.raises(OSError):
        capture_before_install(marker, [
            ("database", old_db), ("employees", old_attachment),
        ], "a" * 40)
    assert old_db.read_bytes() == b"opaque-old-sqlcipher-evidence"
    assert (old_attachment / "receipt.pdf").read_bytes() == b"original-employee-pdf"
    assert not marker.exists()


def test_recovery_advisory_notice_failure_never_grants_write(monkeypatch):
    from threading import RLock
    from centermanager.database import mutation_authority
    from centermanager.platform import recovery_review_notices, write_recovery
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(lock=RLock(), closed=True),
    )
    class Journal:
        journal = Path("/nonexistent/recovery/journal.json")
        def inspect(self):
            raise ValueError("corrupt old journal")
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", Journal)
    def bad_notice(*args, **kwargs):
        raise OSError("read-only recovery notice directory")
    monkeypatch.setattr(recovery_review_notices, "RecoveryReviewNotices", bad_notice)
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: "a" * 40,
        observe_remote_main_commit=lambda: "a" * 40,
    )
    sync = StartupSynchronization.__new__(StartupSynchronization)
    sync._provider = provider
    sync._initial_main_receipt_allowed = False
    assert sync._prepare_authoritative_startup_replacement() is True
    assert sync._review_only_reset_requested is True
    assert sync._review_notice_path is None
    assert sync._initial_main_receipt_allowed is False


def test_schema_and_authority_gates_remain_fail_closed():
    source = Path(startup_module.__file__).read_text(encoding="utf-8")
    assert "inspect_authoritative_database_for_startup(repo_db)" in source
    assert "self._accepted_startup_main_oid" in source
    assert "session_module.quiesce_runtime_db()" in source
    assert "self._rollback_failed_install_all()" in source
    migration = Path(__file__).resolve().parents[1] / "src/centermanager/database/migration.py"
    text = migration.read_text(encoding="utf-8")
    assert "command.upgrade(config, \"head\")" in text
    assert "_validate_post_upgrade_schema(connection, config)" in text
