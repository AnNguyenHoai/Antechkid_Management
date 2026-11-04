"""CLEAN receipt may not depend on volatile SQLite reader SHM sidecars."""
import pytest

from centermanager.platform.write_recovery import RecoveryRequired, WriteRecoveryJournal


def _receipt_journal(tmp_path, *, wal_pending=False, current=None):
    runtime = tmp_path / "runtime"
    repository = runtime / "repository"
    (repository / "database").mkdir(parents=True)
    database = runtime / "Database" / "center.db"
    database.parent.mkdir()
    database.write_bytes(b"accepted-migrated-db")
    journal = WriteRecoveryJournal.__new__(WriteRecoveryJournal)
    journal.runtime = runtime
    journal.repository = repository
    journal.database = database
    journal.root = tmp_path / "runtime.write-recovery"
    journal.journal = journal.root / "journal.json"
    receipt = {
        "status": "CLEAN", "publication": "VERIFIED",
        "published_runtime_sha256": __import__("hashlib").sha256(
            database.read_bytes()
        ).hexdigest(),
        "accepted_local_files": {
            "database/center.db": "accepted",
            "database/center.db-shm": "old-index",
        },
        "repository_id": "repo", "published_oid": "main",
    }
    journal.inspect = lambda: receipt
    journal._wal_pending = lambda: wal_pending
    journal._local_files = lambda: (
        {"database/center.db": "accepted",
         "database/center.db-shm": "new-index",
         "database/center.db-wal": "empty"}
        if current is None else current
    )
    journal._repository_id = lambda: "repo"
    journal._git = lambda *args: {
        ("rev-parse", "HEAD"): "main",
        ("rev-parse", "@{upstream}"): "main",
        ("status", "--porcelain", "--untracked-files=all"): "",
    }[args]
    return journal


def test_reader_created_shm_does_not_invalidate_clean_receipt(tmp_path):
    journal = _receipt_journal(tmp_path)
    journal.assert_replaceable()


def test_nonempty_wal_remains_fail_closed_despite_sidecar_filter(tmp_path):
    journal = _receipt_journal(tmp_path, wal_pending=True)
    with pytest.raises(RecoveryRequired):
        journal.assert_replaceable()


def test_changed_database_fingerprint_remains_fail_closed(tmp_path):
    journal = _receipt_journal(tmp_path, current={
        "database/center.db": "unauthorized-mutation",
        "database/center.db-shm": "reader",
    })
    with pytest.raises(RecoveryRequired):
        journal.assert_replaceable()


def test_changed_business_attachment_remains_fail_closed(tmp_path):
    journal = _receipt_journal(tmp_path, current={
        "database/center.db": "accepted",
        "attachments/student.txt": "unaccepted",
    })
    with pytest.raises(RecoveryRequired):
        journal.assert_replaceable()
