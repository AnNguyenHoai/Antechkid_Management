"""REC-635 modern startup rollback: HMAC binds exact old DB + WAL to notice."""
import json
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.recovery_review_notices import RecoveryReviewNotices
from centermanager.platform.recovery_rollback_evidence import (
    bind_startup_rollback, verify_startup_rollback, reconstructed_readonly_snapshot,
)


def _data(tmp_path):
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()
    journal = root / "journal.json"
    journal.write_text(json.dumps({"status": "OPEN", "session_id": "old-write"}))
    notices = RecoveryReviewNotices(SimpleNamespace(
        root=root, journal=journal, runtime=tmp_path / "runtime",
    ))
    notice_file = notices.record(observed_main_oid="a" * 40)
    notice = notices.validate_notice(notice_file)
    rollback = root / "startup-rollbacks" / "old-instance"
    rollback.mkdir(parents=True)
    return notices, notice, notice_file, rollback


def _sqlite_rollback(tmp_path, rollback):
    source = tmp_path / "original.db"
    db = sqlite3.connect(str(source))
    assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    db.execute("CREATE TABLE receipts (id INTEGER PRIMARY KEY, amount INTEGER)")
    db.commit()
    db.execute("INSERT INTO receipts VALUES (1, 1200000)")
    db.commit()
    shutil.copyfile(source, rollback / "center.db")
    wal = source.with_name(source.name + "-wal")
    assert wal.is_file()
    shutil.copyfile(wal, rollback / "center.db-wal")
    shm = source.with_name(source.name + "-shm")
    if shm.is_file():
        shutil.copyfile(shm, rollback / "center.db-shm")
    db.close()


def test_signed_startup_wal_is_reconstructed_without_modifying_backup(tmp_path):
    notices, notice, notice_file, rollback = _data(tmp_path)
    _sqlite_rollback(tmp_path, rollback)
    key = bytes(range(32))
    proof = bind_startup_rollback(
        notices, notice_file, rollback, encryption_key=key
    )
    assert proof.is_file()
    before = {p.name: p.read_bytes() for p in rollback.iterdir()}
    with reconstructed_readonly_snapshot(
        notices, notice, encryption_key=key
    ) as (snapshot, old_key):
        assert old_key is None
        # Canonical snapshot includes the committed row from detached WAL.
        conn = sqlite3.connect(snapshot.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            assert conn.execute("SELECT amount FROM receipts").fetchone() == (1200000,)
        finally:
            conn.close()
    assert before == {p.name: p.read_bytes() for p in rollback.iterdir()}
    assert verify_startup_rollback(notices, notice, encryption_key=key) == rollback


def test_tampered_rollback_never_becomes_verified(tmp_path):
    notices, notice, notice_file, rollback = _data(tmp_path)
    sqlite3.connect(str(rollback / "center.db")).close()
    key = bytes(range(32))
    bind_startup_rollback(notices, notice_file, rollback, encryption_key=key)
    with (rollback / "center.db").open("ab") as out:
        out.write(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_startup_rollback(notices, notice, encryption_key=key)


def test_wrong_key_cannot_authenticate_proof(tmp_path):
    notices, notice, notice_file, rollback = _data(tmp_path)
    sqlite3.connect(str(rollback / "center.db")).close()
    bind_startup_rollback(notices, notice_file, rollback, encryption_key=b"a" * 32)
    with pytest.raises(ValueError, match="authentication"):
        verify_startup_rollback(notices, notice, encryption_key=b"b" * 32)


def test_missing_rollback_proof_must_not_compare(tmp_path):
    notices, notice, _notice_file, _rollback = _data(tmp_path)
    with pytest.raises(ValueError, match="no signed proof"):
        verify_startup_rollback(notices, notice, encryption_key=b"a" * 32)


def test_repeated_bind_keeps_original_evidence(tmp_path):
    notices, notice, notice_file, rollback = _data(tmp_path)
    sqlite3.connect(str(rollback / "center.db")).close()
    key = b"a" * 32
    first = bind_startup_rollback(notices, notice_file, rollback, encryption_key=key)
    before = first.read_bytes()
    assert bind_startup_rollback(notices, notice_file, rollback, encryption_key=key) == first
    assert first.read_bytes() == before
