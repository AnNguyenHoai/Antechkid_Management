"""Discard-on-restart must never turn an uncertain MAIN into a CLEAN receipt."""
import json
from pathlib import Path

import pytest

from centermanager.platform.write_recovery import RecoveryRequired, WriteRecoveryJournal


def _journal(tmp_path, monkeypatch, *, wal=False, dirty=False):
    runtime = tmp_path / "runtime"
    repository = runtime / "repository"
    dbdir = runtime / "Database"
    repository.mkdir(parents=True)
    (repository / "database").mkdir()
    dbdir.mkdir()
    (dbdir / "center.db").write_bytes(b"accepted-sqlcipher-bytes")
    (repository / "database" / "center.db").write_bytes(b"accepted-sqlcipher-bytes")
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()
    journal = WriteRecoveryJournal.__new__(WriteRecoveryJournal)
    journal.runtime = runtime
    journal.repository = repository
    journal.database = dbdir / "center.db"
    journal.root = root
    journal.journal = root / "journal.json"
    journal.journal.write_text("{old-unreadable-journal", encoding="utf-8")
    journal._wal_pending = lambda: wal
    journal._repository_id = lambda: "verified-repository-id"
    journal._local_files = lambda: {"database/center.db": "hash"}
    def git(*args):
        if args == ("rev-parse", "HEAD") or args == ("rev-parse", "@{upstream}"):
            return "accepted"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return "dirty" if dirty else ""
        raise AssertionError(args)
    journal._git = git
    return journal


def test_verified_main_replaces_stale_journal_only_after_install(tmp_path, monkeypatch):
    journal = _journal(tmp_path, monkeypatch)
    journal.record_authoritative_restart(
        accepted_main="accepted", observe_main=lambda: "accepted"
    )
    receipt = json.loads(journal.journal.read_text(encoding="utf-8"))
    assert receipt["status"] == "CLEAN"
    assert receipt["published_oid"] == "accepted"
    assert receipt["publication"] == "VERIFIED"
    assert receipt["release"] == "VERIFIED"


@pytest.mark.parametrize("observation,wal,dirty", [
    (None, False, False),
    ("newer-main", False, False),
    ("accepted", True, False),
    ("accepted", False, True),
])
def test_uncertain_install_never_overwrites_previous_journal(
    tmp_path, monkeypatch, observation, wal, dirty
):
    journal = _journal(tmp_path, monkeypatch, wal=wal, dirty=dirty)
    with pytest.raises(RecoveryRequired):
        journal.record_authoritative_restart(
            accepted_main="accepted", observe_main=lambda: observation
        )
    assert journal.journal.read_text(encoding="utf-8") == "{old-unreadable-journal"
