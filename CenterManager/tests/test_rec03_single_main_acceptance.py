"""REC-03: only a verified Git MAIN may start a fresh WRITE recovery session."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.manual_review_backup import (
    preserve_workspace_for_manual_review,
)
from centermanager.platform.write_recovery import (
    RecoveryRequired, WriteRecoveryJournal,
)


@pytest.fixture
def context(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    repo = runtime / "repository"
    (repo / ".git").mkdir(parents=True)
    (repo / "database").mkdir()
    (repo / "database" / "center.db").write_bytes(b"accepted MAIN")
    database_dir = runtime / "Database"
    database_dir.mkdir()
    database = database_dir / "center.db"
    database.write_bytes(b"UNPUBLISHED-local-DB")
    (database_dir / "center.db-wal").write_bytes(b"unpublished WAL")
    (runtime / "metadata").mkdir()
    (runtime / "Attachment").mkdir()
    paths = SimpleNamespace(
        runtime_root=runtime, database_dir=database_dir,
        metadata_dir=runtime / "metadata", attachment_dir=runtime / "Attachment",
    )
    journal = WriteRecoveryJournal(paths)
    journal.root.mkdir()
    journal.journal.write_text('{"format":1,"status":"OPEN","session":"OLD"}')
    archive = preserve_workspace_for_manual_review(journal, reason="old-unpublished")
    database.write_bytes(b"accepted MAIN")
    (database_dir / "center.db-wal").unlink()
    oid = "a" * 40

    def fake_git(*args):
        if args[0] == "status":
            return ""
        if args[0] == "config":
            return "https://example.invalid/authoritative.git"
        if args[0] == "rev-parse":
            return oid
        raise AssertionError(args)

    monkeypatch.setattr(journal, "_git", fake_git)
    provider = SimpleNamespace(
        _verified_manual_main_oid=oid,
        _verified_manual_backup_path=str(archive.resolve()),
        observe_remote_main_commit=lambda: oid,
    )
    return journal, provider, archive, oid


def test_new_clean_receipt_after_old_recovery_preserved(context):
    journal, provider, archive, oid = context
    old = journal.journal.read_bytes()
    journal.record_verified_manual_reset(
        provider=provider, accepted_main=oid, archive=archive,
    )
    document = journal.inspect()
    assert document["status"] == "CLEAN"
    assert document["publication"] == "VERIFIED"
    assert document["published_oid"] == oid
    assert document["manual_review_archive"] == str(archive)
    assert (archive / "recovery" / "journal.json").read_bytes() == old
    assert (archive / "database" / "center.db").read_bytes() == b"UNPUBLISHED-local-DB"
    assert (archive / "database" / "center.db-wal").read_bytes() == b"unpublished WAL"
    assert not hasattr(provider, "_verified_manual_main_oid")
    journal.assert_replaceable()


def test_lost_archive_blocks_new_receipt_without_touching_old_recovery(context):
    journal, provider, archive, oid = context
    before = journal.journal.read_bytes()
    (archive / "database" / "center.db").write_bytes(b"tampered")
    with pytest.raises(Exception, match="backup"):
        journal.record_verified_manual_reset(
            provider=provider, accepted_main=oid, archive=archive,
        )
    assert journal.journal.read_bytes() == before


def test_remote_main_oid_change_blocks_receipt(context):
    journal, provider, archive, oid = context
    provider.observe_remote_main_commit = lambda: "b" * 40
    before = journal.journal.read_bytes()
    with pytest.raises(RecoveryRequired, match="Independent MAIN verification"):
        journal.record_verified_manual_reset(
            provider=provider, accepted_main=oid, archive=archive,
        )
    assert journal.journal.read_bytes() == before


def test_app_requires_new_receipt_before_authentication():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    source = (root / "app.py").read_text(encoding="utf-8")
    assert "record_verified_manual_reset(" in source
    assert source.index("record_verified_manual_reset(") < source.index("login_dialog = LoginDialog(")
    assert "if manual_reset_main is not None:" in source
    assert "None if manual_reset_main is not None else startup_journal.inspect()" in source
    assert "accept_isolated_runtime" not in source
