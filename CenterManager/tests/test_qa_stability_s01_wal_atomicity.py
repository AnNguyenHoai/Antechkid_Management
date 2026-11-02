"""QA-S01: disposable WAL publication snapshot fault-injection tests.

No production database, credentials, external Git remote or actual WRITE lock.
Unencrypted synthetic sqlite is deliberate here; SQLCipher is separately covered
by test_qa_p0_recovery_fault_injection.py and E1B1 integration cases.
"""
import sqlite3

import pytest

from centermanager.database import wal_safety


@pytest.fixture
def synthetic_runtime(tmp_path, monkeypatch):
    dbdir = tmp_path / "Database"
    dbdir.mkdir()
    db = dbdir / "center.db"
    connection = sqlite3.connect(db)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO items (value) VALUES ('COMMITTED')")
    connection.commit()
    connection.close()

    class Paths:
        database_dir = dbdir

    monkeypatch.setattr(wal_safety, "get_paths", lambda: Paths())
    monkeypatch.setattr(wal_safety, "database_encryption_required", lambda: False)
    import centermanager.database.session as session
    # A checkpoint permit is valid only inside the actual process maintenance fence.
    # This isolated fixture supplies that fence without manipulating global
    # production engine/session factories or touching a real runtime.
    from centermanager.database.engine import (
        begin_runtime_db_maintenance,
        end_runtime_db_maintenance,
    )
    monkeypatch.setattr(session, "quiesce_runtime_db", begin_runtime_db_maintenance)
    monkeypatch.setattr(session, "refresh_runtime_db", end_runtime_db_maintenance)
    yield db
    end_runtime_db_maintenance()


def _values(path):
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        return connection.execute("SELECT value FROM items ORDER BY id").fetchall()


def test_wal_complete_snapshot_reopens_with_committed_rows(synthetic_runtime, tmp_path):
    with wal_safety.runtime_database_publication_snapshot() as snapshot:
        assert _values(snapshot) == [("COMMITTED",)]
        snapshot_name = snapshot
        with sqlite3.connect(synthetic_runtime) as db:
            db.execute("INSERT INTO items (value) VALUES ('AFTER_SNAPSHOT')")
        assert _values(snapshot) == [("COMMITTED",)]
    assert not snapshot_name.exists()
    assert _values(synthetic_runtime) == [("COMMITTED",), ("AFTER_SNAPSHOT",)]


def test_snapshot_copy_fault_keeps_live_committed_db(synthetic_runtime, monkeypatch):
    real_copy = wal_safety.shutil.copy2

    def fail_snapshot(src, dst, *args, **kwargs):
        if "publish-snapshot-" in str(dst):
            raise OSError("QA injected snapshot copy failure")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(wal_safety.shutil, "copy2", fail_snapshot)
    with pytest.raises(OSError, match="injected"):
        with wal_safety.runtime_database_publication_snapshot():
            pytest.fail("snapshot should not be yielded")
    assert _values(synthetic_runtime) == [("COMMITTED",)]
    assert not list(synthetic_runtime.parent.glob("*.publish-snapshot-*.tmp"))


def test_destination_replace_fault_preserves_old_artifact(synthetic_runtime, tmp_path, monkeypatch):
    target = tmp_path / "repository" / "database" / "center.db"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"OLD_ACCEPTED_BYTES")
    real_replace = wal_safety.os.replace

    def deny_replace(src, dst):
        if str(dst) == str(target):
            raise OSError("QA injected rename denial")
        return real_replace(src, dst)

    monkeypatch.setattr(wal_safety.os, "replace", deny_replace)
    with pytest.raises(OSError, match="rename denial"):
        wal_safety.copy_runtime_database_for_publish(target)
    assert target.read_bytes() == b"OLD_ACCEPTED_BYTES"
    assert _values(synthetic_runtime) == [("COMMITTED",)]
    assert not list(target.parent.glob("*.publish-copy-*.tmp"))
