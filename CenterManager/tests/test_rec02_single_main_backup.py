"""REC-02 Git-MAIN-first single-runtime temporary Recovery backup contracts."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.manual_review_backup import (
    ManualBackupError,
    preserve_workspace_for_manual_review,
    verify_manual_review_backup,
)
from centermanager.platform.sync.startup_sync import StartupSynchronization


@pytest.fixture
def legacy(tmp_path):
    runtime = tmp_path / "runtime"
    repository = runtime / "repository"
    (repository / ".git").mkdir(parents=True)
    (repository / "database").mkdir()
    (repository / "database" / "center.db").write_bytes(b"MAIN source")
    database = runtime / "Database"
    database.mkdir(parents=True)
    (database / "center.db").write_bytes(b"unpublished local")
    (database / "center.db-wal").write_bytes(b"unpublished WAL")
    attachments = runtime / "Attachment"
    attachments.mkdir()
    (attachments / "receipt.bin").write_bytes(b"personal receipt")
    metadata = runtime / "metadata"
    metadata.mkdir()
    config = runtime / "Config"
    config.mkdir()
    (config / "database_key.dpapi").write_bytes(b"old Windows DPAPI key")
    archive_root = tmp_path / "runtime.write-recovery"
    archive_root.mkdir()
    (archive_root / "journal.json").write_text('{"status":"OPEN","local":"old"}')
    paths = SimpleNamespace(
        runtime_root=runtime, database_dir=database, metadata_dir=metadata,
        attachment_dir=attachments,
    )
    from centermanager.platform.write_recovery import WriteRecoveryJournal
    journal = WriteRecoveryJournal(paths)
    return journal


def test_manual_archive_keeps_db_wal_receipt_and_original_recovery_log(legacy):
    archive = preserve_workspace_for_manual_review(legacy, reason="unpublished")
    verify_manual_review_backup(archive)
    assert (archive / "database" / "center.db").read_bytes() == b"unpublished local"
    assert (archive / "database" / "center.db-wal").read_bytes() == b"unpublished WAL"
    assert (archive / "attachments" / "receipt.bin").read_bytes() == b"personal receipt"
    assert (archive / "config" / "database_key.dpapi").read_bytes() == b"old Windows DPAPI key"
    assert (archive / "recovery" / "journal.json").read_bytes() == b'{"status":"OPEN","local":"old"}'
    assert legacy.database.read_bytes() == b"unpublished local"
    assert legacy.journal.read_text() == '{"status":"OPEN","local":"old"}'
    assert (archive / "manifest.json").exists()


def test_archive_tamper_detected_without_modifying_original(legacy):
    archive = preserve_workspace_for_manual_review(legacy, reason="unpublished")
    (archive / "database" / "center.db-wal").write_bytes(b"tampered")
    with pytest.raises(ManualBackupError):
        verify_manual_review_backup(archive)
    assert legacy.database.with_name("center.db-wal").read_bytes() == b"unpublished WAL"


@pytest.mark.parametrize("broken_journal", ['{bad-json', '{"status":"OPEN"}'])
def test_git_main_startup_archives_old_journal_and_allows_single_runtime(
    legacy, monkeypatch, broken_journal
):
    from centermanager.platform import write_recovery
    from centermanager.database import mutation_authority
    legacy.journal.write_text(broken_journal)
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: legacy)
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(
            lock=__import__("threading").RLock(), closed=True,
        ),
    )
    oid = "a" * 40
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: oid,
        observe_remote_main_commit=lambda: oid,
    )
    fake = SimpleNamespace(
        _provider=provider, _initial_main_receipt_allowed=False,
        _manual_review_backup=None,
    )
    assert StartupSynchronization._prepare_authoritative_startup_replacement(fake)
    assert fake._manual_reset_requested
    assert fake._accepted_startup_main_oid == oid
    assert fake._startup_reconciled_unaccepted_local
    verify_manual_review_backup(fake._manual_review_backup)
    assert (fake._manual_review_backup / "recovery" / "journal.json").read_text() == broken_journal


def test_no_journal_but_existing_business_data_preserved_for_initial_main_receipt(
    legacy, monkeypatch,
):
    from centermanager.platform import write_recovery
    from centermanager.database import mutation_authority
    legacy.journal.unlink()
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: legacy)
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(
            lock=__import__("threading").RLock(), closed=True,
        ),
    )
    oid = "a" * 40
    fake = SimpleNamespace(
        _provider=SimpleNamespace(
            get_fetched_remote_main_commit=lambda: oid,
            observe_remote_main_commit=lambda: oid,
        ),
        _initial_main_receipt_allowed=False,
        _manual_review_backup=None,
    )
    assert StartupSynchronization._prepare_authoritative_startup_replacement(fake)
    assert fake._initial_main_receipt_allowed
    assert not fake._manual_reset_requested
    assert (fake._manual_review_backup / "database" / "center.db").read_bytes() == b"unpublished local"


def test_archive_rejects_symlinked_workspace_without_overwriting_original(legacy, tmp_path):
    original = legacy.paths.attachment_dir / "unsafe"
    try:
        original.symlink_to(tmp_path / "outside")
    except OSError:
        pytest.skip("Symlink permissions restricted on Windows runner")
    with pytest.raises(ManualBackupError):
        preserve_workspace_for_manual_review(legacy, reason="symlink")
    assert legacy.database.read_bytes() == b"unpublished local"


def test_no_runtime_db_but_legacy_business_material_is_not_discarded(
    legacy, monkeypatch,
):
    from centermanager.platform import write_recovery
    from centermanager.database import mutation_authority
    legacy.database.unlink()
    legacy.database.with_name("center.db-wal").unlink()
    legacy.journal.unlink()
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: legacy)
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(
            lock=__import__("threading").RLock(), closed=True,
        ),
    )
    oid = "a" * 40
    fake = SimpleNamespace(
        _provider=SimpleNamespace(
            get_fetched_remote_main_commit=lambda: oid,
            observe_remote_main_commit=lambda: oid,
        ),
        _initial_main_receipt_allowed=False,
        _manual_review_backup=None,
    )
    assert StartupSynchronization._prepare_authoritative_startup_replacement(fake)
    assert fake._initial_main_receipt_allowed is True
    assert (fake._manual_review_backup / "attachments" / "receipt.bin").read_bytes() == b"personal receipt"
    assert (fake._manual_review_backup / "config" / "database_key.dpapi").read_bytes() == b"old Windows DPAPI key"
    verify_manual_review_backup(fake._manual_review_backup)


def test_long_nested_recovery_capture_is_preserved_in_short_flat_archive(legacy):
    """WinError 206 regression: archive adds ~50 chars to an existing capture."""
    deep = (legacy.root / "captures" / ("c" * 32) / "exports"
            / "SessionReports" / "Class_1_K3_Scratch"
            / "Lesson_3_Học về Function")
    deep.mkdir(parents=True)
    source = deep / "report.txt"
    source.write_bytes(b"preserve this unpublished lesson report")

    archive = preserve_workspace_for_manual_review(legacy, reason="win206")
    verify_manual_review_backup(archive)
    logical = "recovery/" + source.relative_to(legacy.root).as_posix()
    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == 2
    entry = manifest["files"][logical]
    assert isinstance(entry, dict)
    assert entry["stored_path"].startswith("long-paths/")
    stored = archive / entry["stored_path"]
    assert len(str(stored)) < len(str(archive / logical))
    assert stored.read_bytes() == source.read_bytes()
    assert source.read_bytes() == b"preserve this unpublished lesson report"

    stored.write_bytes(b"tampered")
    with pytest.raises(ManualBackupError):
        verify_manual_review_backup(archive)
    assert source.read_bytes() == b"preserve this unpublished lesson report"


def test_prior_manual_archives_are_not_recursively_backed_up(legacy):
    previous = legacy.root / "manual-review" / ("b" * 32) / "recovery" / "captures"
    previous.mkdir(parents=True)
    (previous / "old.txt").write_text("historical archive", encoding="utf-8")
    archive = preserve_workspace_for_manual_review(legacy, reason="avoid-recursion")
    verify_manual_review_backup(archive)
    document = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    assert not any("manual-review" in name for name in document["files"])


def test_legacy_format_one_manifest_remains_verifiable(legacy):
    archive = preserve_workspace_for_manual_review(legacy, reason="old-version")
    manifest = archive / "manifest.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    assert all(isinstance(value, str) for value in document["files"].values())
    document["format"] = 1
    manifest.write_text(json.dumps(document), encoding="utf-8")
    verify_manual_review_backup(archive)
