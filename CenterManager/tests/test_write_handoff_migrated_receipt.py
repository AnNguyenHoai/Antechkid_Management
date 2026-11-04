"""Authoritative WRITE handoff may migrate MAIN without weakening recovery."""
from pathlib import Path

import pytest

from centermanager.platform.write_recovery import (
    RecoveryRequired, WriteRecoveryJournal,
)


def _make_journal(tmp_path, *, state="CLEAN", wal=False, dirty=False):
    runtime = tmp_path / "runtime"
    repo = runtime / "repository"
    (repo / "database").mkdir(parents=True)
    dbdir = runtime / "Database"
    dbdir.mkdir()
    db = dbdir / "center.db"
    db.write_bytes(b"migrated-head-v44")
    (repo / "database" / "center.db").write_bytes(b"main-schema-v42")
    j = WriteRecoveryJournal.__new__(WriteRecoveryJournal)
    j.runtime = runtime
    j.repository = repo
    j.database = db
    j.root = tmp_path / "runtime.write-recovery"
    j.journal = j.root / "journal.json"
    before = dict(
        format=1, runtime=str(runtime), status=state,
        publication="VERIFIED", repository_id="same-repo",
        published_oid="old-main",
        published_runtime_sha256="old-db-hash",
        accepted_local_files={"old.pdf": "hash"},
    )
    data = dict(before)
    j.inspect = lambda: dict(data)
    j._repository_id = lambda: "same-repo"
    j._wal_pending = lambda: wal
    j._local_files = lambda: {"new.pdf": "new-hash"}
    j._git = lambda *args: {
        ("rev-parse", "HEAD"): "new-main",
        ("rev-parse", "@{upstream}"): "new-main",
        ("status", "--porcelain", "--untracked-files=all"): "dirty" if dirty else "",
    }[args]
    j.assert_replaceable = lambda: None
    writes = []

    def update(**changes):
        data.update(changes)
        writes.append(dict(changes))
    j.update = update
    return j, before, writes


def test_migrated_authoritative_main_is_accepted_without_byte_equality(tmp_path):
    j, before, writes = _make_journal(tmp_path)
    j.record_verified_handoff_install(
        before=before, accepted_main="new-main", observe_main=lambda: "new-main"
    )
    assert len(writes) == 1
    assert writes[0]["status"] == "CLEAN"
    assert writes[0]["published_oid"] == "new-main"
    assert writes[0]["accepted_local_files"] == {"new.pdf": "new-hash"}
    assert len(writes[0]["published_runtime_sha256"]) == 64


@pytest.mark.parametrize("state,remote,wal,dirty", [
    ("OPEN", "new-main", False, False),
    ("PUBLISHING", "new-main", False, False),
    ("CLEAN", None, False, False),
    ("CLEAN", "advanced-main", False, False),
    ("CLEAN", "new-main", True, False),
    ("CLEAN", "new-main", False, True),
])
def test_unsafe_handoff_never_writes_clean_receipt(tmp_path, state, remote, wal, dirty):
    j, before, writes = _make_journal(tmp_path, state=state, wal=wal, dirty=dirty)
    with pytest.raises(RecoveryRequired):
        j.record_verified_handoff_install(
            before=before, accepted_main="new-main", observe_main=lambda: remote
        )
    assert writes == []
