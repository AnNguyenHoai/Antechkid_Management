"""Windows CI: real SQLCipher WAL and user-scoped DPAPI recovery round trip.

No test secrets, production credentials, app runtime, or external Git remote.
"""
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.database import encryption
from centermanager.platform import recovery_rollback_evidence as evidence
from centermanager.platform.recovery_review_notices import RecoveryReviewNotices


@pytest.mark.skipif(os.name != "nt", reason="Real Windows DPAPI is required")
def test_actual_dpapi_sqlcipher_rollback_wal_roundtrip(tmp_path, monkeypatch):
    sqlcipher = encryption.load_sqlcipher_driver()
    key = bytes(range(32))
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()
    journal_file = root / "journal.json"
    journal_file.write_text(json.dumps({"session_id": "real-dpapi", "status": "OPEN"}))
    notices = RecoveryReviewNotices(SimpleNamespace(
        root=root, journal=journal_file, runtime=tmp_path / "runtime"
    ))
    path = notices.record(observed_main_oid="a" * 40)
    notice = notices.validate_notice(path)
    rollback = root / "startup-rollbacks" / "instance"
    rollback.mkdir(parents=True)
    key_bundle = rollback / "database_key.dpapi"

    # The actual Windows crypt32 DPAPI protection is exercised here.
    encryption.DatabaseKeyStore(key_bundle).provision(key)
    assert encryption.DatabaseKeyStore(key_bundle).load() == key
    assert key.hex() not in key_bundle.read_text(encoding="utf-8")

    original = tmp_path / "old.sqlcipher"
    conn = sqlcipher.connect(str(original))
    encryption.apply_sqlcipher_key(conn, key)
    assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
    conn.execute("CREATE TABLE incomes (id INTEGER PRIMARY KEY, amount INTEGER)")
    conn.commit()
    conn.execute("INSERT INTO incomes VALUES (1, 1200000)")
    conn.commit()
    shutil.copy2(original, rollback / "center.db")
    shutil.copy2(Path(str(original) + "-wal"), rollback / "center.db-wal")
    shm = Path(str(original) + "-shm")
    if shm.exists():
        shutil.copy2(shm, rollback / "center.db-shm")
    conn.close()

    # Only a synthetic per-test key is used to sign the proof; the DB's
    # original key is still loaded from the real DPAPI bundle on recovery.
    monkeypatch.setattr(evidence, "_key", lambda explicit: key if explicit is None else explicit)
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: True)
    baseline = {p.name: evidence._hash(p) for p in rollback.iterdir()}
    evidence.bind_startup_rollback(notices, path, rollback)
    with evidence.reconstructed_readonly_snapshot(notices, notice) as (snapshot, recovered_key):
        assert recovered_key == key
        assert not encryption.is_plaintext_sqlite_file(snapshot)
        reader = sqlcipher.connect(snapshot.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            encryption.apply_sqlcipher_key(reader, recovered_key)
            reader.execute("PRAGMA query_only=ON")
            assert reader.execute("SELECT amount FROM incomes").fetchone() == (1200000,)
        finally:
            reader.close()
    assert baseline == {p.name: evidence._hash(p) for p in rollback.iterdir()}
