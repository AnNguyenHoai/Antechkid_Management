"""Fresh Git installations must obtain a receipt after Alembic, not before.

A missing legacy receipt alone never authorizes accepting local bytes.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.write_recovery import RecoveryRequired, WriteRecoveryJournal


def make_journal(tmp_path, *, existing=False, wal=False, dirty=False):
    runtime = tmp_path / "runtime"
    repository = runtime / "repository"
    (repository / "database").mkdir(parents=True)
    database_dir = runtime / "Database"
    database_dir.mkdir()
    database = database_dir / "center.db"
    database.write_bytes(b"schema-migrated-runtime-db")
    (repository / "database" / "center.db").write_bytes(b"accepted-main-db-before-migration")
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()
    journal = WriteRecoveryJournal.__new__(WriteRecoveryJournal)
    journal.paths = SimpleNamespace(
        metadata_dir=runtime / "metadata", attachment_dir=runtime / "Attachment"
    )
    journal.runtime = runtime
    journal.repository = repository
    journal.database = database
    journal.root = root
    journal.journal = root / "journal.json"
    if existing:
        journal.journal.write_text("old-journal", encoding="utf-8")
    journal._wal_pending = lambda: wal
    journal._repository_id = lambda: "verified-repo-id"
    journal._local_files = lambda: {"database/center.db": "migrated-hash"}
    journal.assert_replaceable = lambda: None

    def git(*args):
        if args in (("rev-parse", "HEAD"), ("rev-parse", "@{upstream}")):
            return "accepted-main"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return "untracked" if dirty else ""
        raise AssertionError(args)
    journal._git = git
    return journal


def test_fresh_install_receipt_accepts_authorized_migrated_schema(tmp_path):
    journal = make_journal(tmp_path)
    provider = SimpleNamespace(
        _fresh_install_main_oid="accepted-main",
        observe_remote_main_commit=lambda: "accepted-main",
    )
    journal.record_verified_fresh_install(provider=provider, accepted_main="accepted-main")

    receipt = json.loads(journal.journal.read_text(encoding="utf-8"))
    assert receipt["status"] == "CLEAN"
    assert receipt["publication"] == "VERIFIED"
    assert receipt["release"] == "VERIFIED"
    assert receipt["published_oid"] == "accepted-main"
    assert receipt["accepted_local_files"] == {"database/center.db": "migrated-hash"}
    assert not hasattr(provider, "_fresh_install_main_oid")


@pytest.mark.parametrize("existing,proof,remote,wal,dirty", [
    (True, True, "accepted-main", False, False),
    (False, False, "accepted-main", False, False),
    (False, True, "changed-main", False, False),
    (False, True, None, False, False),
    (False, True, "accepted-main", True, False),
    (False, True, "accepted-main", False, True),
])
def test_no_false_clean_receipt(tmp_path, existing, proof, remote, wal, dirty):
    journal = make_journal(tmp_path, existing=existing, wal=wal, dirty=dirty)
    provider = SimpleNamespace(
        observe_remote_main_commit=lambda: remote,
    )
    if proof:
        provider._fresh_install_main_oid = "accepted-main"
    with pytest.raises(RecoveryRequired):
        journal.record_verified_fresh_install(provider=provider, accepted_main="accepted-main")
    if existing:
        assert journal.journal.read_text(encoding="utf-8") == "old-journal"
    else:
        assert not journal.journal.exists()
