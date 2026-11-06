"""RV-04: review state, skip behavior and privacy-safe UI regression."""
import json
import os

import pytest

from tests.test_rv03_recovery_case_registry import FakeJournal, MAIN
from centermanager.platform.recovery_case_registry import RecoveryCaseRegistry
from centermanager.platform.write_recovery import RecoveryRequired


@pytest.fixture
def cases(tmp_path, monkeypatch):
    monkeypatch.setattr(RecoveryCaseRegistry, "_key", lambda self: bytes(range(32)))
    journal = FakeJournal(tmp_path)
    registry = RecoveryCaseRegistry(journal)
    first = registry.register_from_reconciled(observed_main_oid=MAIN)
    return journal, registry, first


def test_review_persists_and_preserves_immutable_backup(cases):
    journal, registry, first = cases
    case_path = registry.root / (first["case_id"] + ".json")
    capture = journal.capture
    assert case_path.is_file() and capture.is_dir()
    assert len(registry.pending_cases()) == 1
    checked = registry.mark_reviewed(first["case_id"])
    assert checked["status"] == "ACKNOWLEDGED"
    assert checked["reviewed_at_utc"]
    assert registry.mark_reviewed(first["case_id"]) == checked
    assert RecoveryCaseRegistry(journal).pending_cases() == []
    assert RecoveryCaseRegistry(journal).get(first["case_id"]) == checked
    assert capture.is_dir()
    assert first["capture_ref"] == checked["capture_ref"]
    assert first["capture_db_sha256"] == checked["capture_db_sha256"]
    assert first["observed_main_oid"] == checked["observed_main_oid"]
    assert len(list(registry.root.glob("*.json"))) == 1


def test_skip_or_close_never_changes_case_file(cases):
    _journal, registry, first = cases
    case_path = registry.root / (first["case_id"] + ".json")
    before = case_path.read_bytes()
    assert len(registry.pending_cases()) == 1  # startup #1: skip
    assert len(RecoveryCaseRegistry(registry.journal).pending_cases()) == 1  # restart
    assert case_path.read_bytes() == before


def test_review_refuses_corrupted_original_capture(cases):
    journal, registry, first = cases
    journal.capture_valid = False
    with pytest.raises(RecoveryRequired):
        registry.mark_reviewed(first["case_id"])
    assert registry.get(first["case_id"])["status"] == "PENDING_REVIEW"


def test_review_refuses_tampered_signed_case(cases):
    _journal, registry, first = cases
    path = registry.root / (first["case_id"] + ".json")
    bad = json.loads(path.read_text(encoding="utf-8"))
    bad["status"] = "ACKNOWLEDGED"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RecoveryRequired, match="inauthentic"):
        registry.mark_reviewed(first["case_id"])


def test_review_does_not_change_journal_or_start_remote_activity(cases):
    journal, registry, first = cases
    document = journal.inspect()
    checked = registry.mark_reviewed(first["case_id"])
    assert checked["status"] == "ACKNOWLEDGED"
    assert journal.inspect() == document  # UI review does not mutate WRITE journal


def test_new_incident_remains_pending_after_prior_review(tmp_path, monkeypatch):
    monkeypatch.setattr(RecoveryCaseRegistry, "_key", lambda self: bytes(range(32)))
    journal = FakeJournal(tmp_path)
    registry = RecoveryCaseRegistry(journal)
    old = registry.register_from_reconciled(observed_main_oid=MAIN)
    registry.mark_reviewed(old["case_id"])
    # Simulate a distinct future incident. Do not alter the old case.
    journal.document["rv03_case_id"] = None
    journal.document["session_id"] = "future-session"
    fresh = registry.register_from_reconciled(observed_main_oid=MAIN)
    assert fresh["case_id"] != old["case_id"]
    assert [c["case_id"] for c in registry.pending_cases()] == [fresh["case_id"]]
    assert registry.get(old["case_id"])["status"] == "ACKNOWLEDGED"


def test_summary_never_exports_names_or_paths(cases):
    from centermanager.ui.recovery_cases_dialog import _summary
    _journal, _registry, first = cases
    summary = _summary(first)
    output = json.dumps(summary, ensure_ascii=False)
    assert "capture_ref" not in summary
    assert "write_session_id" not in summary
    assert "student" not in output.lower()
    assert "salary" not in output.lower()
    assert "UNKNOWN" in output
    assert "UNVERIFIED" in output


def test_dialog_skip_does_not_persist_review(cases, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from centermanager.ui.recovery_cases_dialog import RecoveryCasesDialog
    app = QApplication.instance() or QApplication([])
    journal, registry, first = cases
    dialog = RecoveryCasesDialog(registry=registry, pending_only=True)
    assert dialog._review.isEnabled()
    dialog.reject()  # Skip / close, not reviewed.
    assert RecoveryCaseRegistry(journal).pending_cases()[0]["case_id"] == first["case_id"]
    dialog.deleteLater()
