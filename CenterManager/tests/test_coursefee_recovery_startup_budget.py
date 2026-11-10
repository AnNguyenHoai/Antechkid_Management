"""Bound advisory Recovery proof work at startup; never block verified MAIN."""
import json
import sqlite3
from types import SimpleNamespace

import pytest

from centermanager.platform import recovery_rollback_evidence as evidence
from centermanager.platform.recovery_review_notices import RecoveryReviewNotices


def test_large_local_rollback_preserved_without_synchronous_full_hash(tmp_path, monkeypatch):
    root = tmp_path / "workspace.write-recovery"
    root.mkdir()
    journal = root / "journal.json"
    journal.write_text(json.dumps({"status": "OPEN", "session_id": "local-old"}), encoding="utf-8")
    notices = RecoveryReviewNotices(SimpleNamespace(
        root=root, journal=journal, runtime=tmp_path / "runtime",
    ))
    notice_file = notices.record(observed_main_oid="a" * 40)
    notice = notices.validate_notice(notice_file)
    rollback = root / "startup-rollbacks" / "old-instance"
    rollback.mkdir(parents=True)
    source = rollback / "center.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE old_local (value TEXT)")
        db.execute("INSERT INTO old_local VALUES ('not published')")
        db.commit()
    assert source.stat().st_size > 1
    original = source.read_bytes()
    monkeypatch.setattr(evidence, "_MAX_STARTUP_PROOF_BYTES", 1)
    with pytest.raises(ValueError, match="bounded startup proof budget"):
        evidence.bind_startup_rollback(
            notices, notice_file, rollback, encryption_key=b"e" * 32,
        )
    assert source.read_bytes() == original
    assert not (notices.root / (notice["id"] + ".rollback-proof.json")).exists()
    with pytest.raises(ValueError, match="no signed proof"):
        evidence.verify_startup_rollback(notices, notice, encryption_key=b"e" * 32)
