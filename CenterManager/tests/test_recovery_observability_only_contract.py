"""Release regression: Recovery logging must NEVER authorize or veto a writer.

These tests operate on synthetic local files, not any production SQLCipher DB,
Git repository, lease, or user profile.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.write_recovery import WriteRecoveryJournal
from centermanager.services.write_transaction import WriteTransactionManager


ROOT = Path(__file__).resolve().parents[1] / "src/centermanager"


def test_corrupt_old_receipt_archived_raw_before_new_advisory_edit(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    db_dir = runtime / "Database"
    db_dir.mkdir()
    paths = SimpleNamespace(runtime_root=runtime, database_dir=db_dir)
    journal = WriteRecoveryJournal(paths)
    journal.root.mkdir()
    old_bytes = b"{corrupt-OPEN-journal-unpublished}"
    journal.journal.write_bytes(old_bytes)
    monkeypatch.setattr(journal, "_git", lambda *args: "a" * 40)
    monkeypatch.setattr(journal, "_repository_id", lambda: "synthetic-git-identity")
    monkeypatch.setattr(journal, "preserve", lambda *args: "synthetic-capture")
    monkeypatch.setattr(journal, "prune_captures", lambda *args: 0)

    journal.begin("edit-2", "a" * 40, {}, advisory=True)

    archived = list((journal.root / "history").glob("advisory-*.json"))
    assert len(archived) == 1
    assert archived[0].read_bytes() == old_bytes
    assert journal.inspect()["status"] == "OPEN"
    assert journal.inspect()["session_id"] == "edit-2"


def test_failed_recovery_logging_cannot_block_independent_write(monkeypatch):
    from centermanager.platform import write_recovery
    from centermanager.database import encryption
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: True)
    monkeypatch.setattr(
        write_recovery, "WriteRecoveryJournal",
        lambda: (_ for _ in ()).throw(OSError("Recovery disk full")),
    )
    tx = WriteTransactionManager.__new__(WriteTransactionManager)
    tx._recovery_journal = None
    assert tx._begin_recovery_journal() is True
    assert tx._recovery_journal is None


def test_start_editing_requires_git_and_lease_not_recovery_receipt():
    source = (ROOT / "services/write_transaction.py").read_text(encoding="utf-8")
    method = source.split("def start_editing(", 1)[1].split(
        "def finish_editing(", 1
    )[0]
    assert "require_replaceable()" not in method
    assert "WriteRecoveryJournal().inspect()" not in method
    assert "request_write" in method
    assert "_verify_first_writer_consistency" in method
    assert "_verify_grant_before_editing()" in method


def test_mutation_gate_never_reads_recovery_ledger_for_permission():
    source = (ROOT / "database/mutation_authority.py").read_text(encoding="utf-8")
    gate_open = source.split("    def open(self):", 1)[1].split(
        "    def _verified_remaining(", 1
    )[0]
    gate_require = source.split("    def require(", 1)[1].split(
        "def authentication_activity_policy(", 1
    )[0]
    assert "journal.inspect()" not in gate_open
    assert "journal.inspect()" not in gate_require
    assert "provider.observe_remote_main_commit() != pinned" in gate_open
    assert "time.monotonic() >= self.deadline" in gate_require
    assert "cm.is_writing()" in gate_require


def test_recovery_failure_cannot_latch_offline_mode():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "_degrade_startup_to_verified_read" not in app
    assert "Recovery receipt unavailable; accepted Git MAIN remains usable" in app
    offline = (ROOT / "platform/sync/offline_read_state.py").read_text(encoding="utf-8")
    assert "_receipt_read_only" not in offline
    assert "protect_read_only_for_process" not in offline


def test_approved_review_skip_only_changes_advisory_notice(tmp_path):
    from centermanager.platform.recovery_review_notices import RecoveryReviewNotices
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()
    journal = root / "journal.json"
    raw = b'{"status":"OPEN","publication":"UNVERIFIED"}'
    journal.write_bytes(raw)
    queue = RecoveryReviewNotices(
        SimpleNamespace(root=root, journal=journal, runtime=tmp_path / "runtime")
    )
    path = queue.record(observed_main_oid="a" * 40)
    case = queue.validate_notice(path)
    assert len(queue.pending()) == 1  # Skip means no mutation
    queue.acknowledge(case["id"])
    assert not queue.pending()
    assert journal.read_bytes() == raw  # Review does not alter business data


def test_corrupt_recovery_audit_does_not_reject_authorized_business_adapter(
    tmp_path, monkeypatch,
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from centermanager.services import recovery_change_outbox as outbox
    from centermanager.platform import write_recovery

    def fail_journal():
        raise OSError("Recovery disk is unavailable")

    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", fail_journal)
    engine = create_engine("sqlite:///:memory:")
    engine._cm_runtime_owned = True
    try:
        with Session(engine) as session:
            assert outbox.record_for_active_write(
                session, module="student", action="UPDATE",
                entity_type="Student", entity_id=101,
            ) is None
            # Audit failure must not poison the business SQL transaction.
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
            session.commit()
    finally:
        engine.dispose()
