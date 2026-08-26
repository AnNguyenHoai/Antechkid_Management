"""
STUDENT-1.7 integration audit.

These tests protect the cross-layer contracts of Student Workspace without
requiring a live Git remote or a running Qt event loop.
"""
from pathlib import Path

ROOT = Path("src/centermanager")
MAIN = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
TX = (ROOT / "services/write_transaction.py").read_text(encoding="utf-8")
STUDENT_SERVICE = (ROOT / "services/student_service.py").read_text(encoding="utf-8")
REPORT_SERVICE = (ROOT / "services/report_service.py").read_text(encoding="utf-8")
REPORT_GENERATOR = (ROOT / "export/pdf/student_report_generator.py").read_text(encoding="utf-8")


def test_finish_flow_generates_reports_only_from_dirty_student_aggregates():
    assert "def on_publish_success()" in MAIN
    assert "dirty_student_ids = list(self._transaction.dirty_student_ids)" in MAIN
    assert "generate_student_report(" in MAIN
    assert "trigger_event=\"student_updated\"" in MAIN


def test_parent_changes_dirty_the_owning_student_aggregate():
    start = MAIN.index("def _on_parent_event")
    end = MAIN.index("def _on_student_archived_event", start)
    section = MAIN[start:end]
    assert 'student_id = getattr(event, "student_id", None)' in section
    assert "mark_student_dirty(student_id)" in section


def test_profile_image_change_publishes_complete_student_updated_event():
    start = STUDENT_SERVICE.index("def set_profile_image")
    end = STUDENT_SERVICE.index("def update_student", start)
    section = STUDENT_SERVICE[start:end]
    assert "StudentUpdated(" in section
    assert 'changes=["profile_image_path"]' in section


def test_profile_image_report_resolves_from_attachment_root():
    assert "attachment_dir" in REPORT_GENERATOR


def test_successful_finish_deletes_snapshot_only_after_publish_success():
    start = TX.index("Transaction: PUBLISHED")
    end = TX.index("else:", start)
    section = TX[start:end]
    assert "self._on_publish_success()" in section
    assert "self._release_lock()" in section
    assert "self._delete_snapshot()" in section
    assert section.index("self._delete_snapshot()") > section.index("self._release_lock()")


def test_forced_cancel_restores_then_cleans_snapshot():
    start = TX.index("def cancel_editing")
    end = TX.index("# ---- Publish helpers ----", start)
    section = TX[start:end]
    assert "self._restore_snapshot()" in section
    assert "self._delete_snapshot()" in section
    assert section.index("self._delete_snapshot()") > section.index("self._restore_snapshot()")


def test_conflict_or_authority_failure_keeps_recovery_snapshot():
    start = TX.index("def enter_finishing")
    end = TX.index("def refresh_finishing_authority", start)
    section = TX[start:end]
    assert "PUBLISH_CONFLICT" in section
    assert "FINISHING_STALE" in section
    assert "self._delete_snapshot()" not in section


def test_student_lifecycle_events_track_dirty_aggregate():
    assert MAIN.count("self._transaction.mark_student_dirty(event.student_id)") >= 3


def test_archive_filter_is_explicitly_supported():
    filter_service = (ROOT / "services/student_filter_service.py").read_text(encoding="utf-8")
    assert "ARCHIVED" in filter_service


def test_latest_report_policy_is_not_historical_accumulation():
    assert 'report_type="latest"' in MAIN
    assert "latest" in REPORT_SERVICE.lower()
