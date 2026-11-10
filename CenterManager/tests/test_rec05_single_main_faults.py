"""REC-05 fault injection for single-active-Git-MAIN manual recovery.

No test may contact the real remote or use production DPAPI credentials.
Each refusal preserves original business database, WAL and raw log bytes.
"""
from pathlib import Path
from types import SimpleNamespace
from threading import RLock

import pytest

from centermanager.platform.sync.manual_review_backup import (
    ManualBackupError, preserve_workspace_for_manual_review,
    verify_manual_review_backup,
)
from centermanager.platform.sync.startup_sync import StartupSynchronization
from centermanager.platform.write_recovery import WriteRecoveryJournal


@pytest.fixture
def legacy(tmp_path):
    runtime = tmp_path / "runtime"
    repo = runtime / "repository"
    (repo / ".git").mkdir(parents=True)
    (repo / "database").mkdir()
    (repo / "database" / "center.db").write_bytes(b"Git MAIN accepted")
    data = runtime / "Database"
    data.mkdir()
    (data / "center.db").write_bytes(b"UNPUBLISHED")
    (data / "center.db-wal").write_bytes(b"PENDING WAL")
    (runtime / "metadata").mkdir()
    (runtime / "Attachment").mkdir()
    journal = WriteRecoveryJournal(SimpleNamespace(
        runtime_root=runtime, database_dir=data,
        metadata_dir=runtime / "metadata",
        attachment_dir=runtime / "Attachment",
    ))
    journal.root.mkdir()
    journal.journal.write_bytes(b'{"status":"OPEN","unpublished":true}')
    return journal


def _unmodified(journal):
    assert journal.database.read_bytes() == b"UNPUBLISHED"
    assert journal.database.with_name("center.db-wal").read_bytes() == b"PENDING WAL"
    assert journal.journal.read_bytes() == b'{"status":"OPEN","unpublished":true}'


def test_archive_creation_crash_does_not_mutate_local_or_accept_partial(legacy, monkeypatch):
    from centermanager.platform.sync import manual_review_backup as module
    original_open = Path.open
    def interrupted(self, *args, **kwargs):
        if "manual-review" in self.parts and self.name == "center.db-wal":
            raise PermissionError("simulated Windows file lock during backup")
        return original_open(self, *args, **kwargs)
    monkeypatch.setattr(Path, "open", interrupted)
    with pytest.raises(PermissionError, match="file lock"):
        preserve_workspace_for_manual_review(legacy, reason="crash")
    _unmodified(legacy)
    for candidate in (legacy.root / "manual-review").iterdir():
        assert not (candidate / "manifest.json").exists()


def test_remote_main_advance_cannot_authorize_backup_or_reset(legacy, monkeypatch):
    from centermanager.platform import write_recovery
    from centermanager.database import mutation_authority
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: legacy)
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(lock=RLock(), closed=True),
    )
    fake = SimpleNamespace(
        _provider=SimpleNamespace(
            get_fetched_remote_main_commit=lambda: "a" * 40,
            observe_remote_main_commit=lambda: "b" * 40,
        ),
        _initial_main_receipt_allowed=False,
    )
    assert not StartupSynchronization._prepare_authoritative_startup_replacement(fake)
    assert not (legacy.root / "manual-review").exists()
    _unmodified(legacy)


def test_invalid_copy_refuses_startup_without_changing_pending_local(legacy, monkeypatch):
    from centermanager.platform import write_recovery
    from centermanager.database import mutation_authority
    from centermanager.platform.sync import manual_review_backup as module
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: legacy)
    monkeypatch.setattr(mutation_authority, "gate_for", lambda: SimpleNamespace(lock=RLock(), closed=True))
    def corrupt(*args, **kwargs):
        raise ManualBackupError("simulated copy/hash failure")
    monkeypatch.setattr(module, "preserve_workspace_for_manual_review", corrupt)
    fake = SimpleNamespace(
        _provider=SimpleNamespace(
            get_fetched_remote_main_commit=lambda: "a" * 40,
            observe_remote_main_commit=lambda: "a" * 40,
        ),
        _initial_main_receipt_allowed=False,
    )
    # Failure of the obsolete recursive archive must not veto authenticated MAIN.
    assert StartupSynchronization._prepare_authoritative_startup_replacement(fake)
    assert fake._review_only_reset_requested is True
    assert fake._review_notice_path is not None
    assert not (legacy.root / "manual-review").exists()
    _unmodified(legacy)


def test_interrupted_acceptance_keeps_old_log_and_evidence(legacy, monkeypatch):
    from centermanager.platform import write_recovery
    archive = preserve_workspace_for_manual_review(legacy, reason="old-write")
    verify_manual_review_backup(archive)
    legacy.database.write_bytes(b"Git MAIN accepted")
    legacy.database.with_name("center.db-wal").unlink()
    oid = "a" * 40
    monkeypatch.setattr(legacy, "_git", lambda *args: "" if args[0] == "status" else (
        "synthetic-origin" if args[0] == "config" else oid
    ))
    provider = SimpleNamespace(
        _verified_manual_main_oid=oid,
        _verified_manual_backup_path=str(archive.resolve()),
        observe_remote_main_commit=lambda: oid,
    )
    def interrupted(*args, **kwargs):
        raise OSError("disk full during receipt")
    monkeypatch.setattr(write_recovery, "_json", interrupted)
    with pytest.raises(OSError, match="disk full"):
        legacy.record_verified_manual_reset(
            provider=provider, accepted_main=oid, archive=archive,
        )
    assert legacy.journal.read_bytes() == b'{"status":"OPEN","unpublished":true}'
    assert (archive / "database" / "center.db").read_bytes() == b"UNPUBLISHED"
    assert (archive / "database" / "center.db-wal").read_bytes() == b"PENDING WAL"


def test_recovery_never_requires_an_alternate_active_runtime():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    app = (root / "app.py").read_text(encoding="utf-8")
    startup = (root / "platform" / "sync" / "startup_sync.py").read_text(encoding="utf-8")
    assert "accept_isolated_runtime" not in app
    assert "prepare_isolated_runtime" not in app
    assert "read_selected_workspace" not in app
    assert "RecoveryReviewNotices" in startup
    assert "reset_verified_main_for_review" in startup
    assert "self._runtime_db_path" in startup
