"""
STUDENT-1.9 — Stability / Regression Gate

Static integration contracts for the completed Student Workspace lifecycle.
This gate protects previously fixed behavior from future refactors.
"""
from pathlib import Path

ROOT = Path("src/centermanager")
MAIN = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
TX = (ROOT / "services/write_transaction.py").read_text(encoding="utf-8")
LIST = (ROOT / "ui/student_workspace/student_list_page.py").read_text(encoding="utf-8")
STUDENT = (ROOT / "services/student_service.py").read_text(encoding="utf-8")
REPORT = (ROOT / "services/report_service.py").read_text(encoding="utf-8")


def _section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_write_transaction_has_explicit_lifecycle_states():
    assert "WriteTransactionState" in TX
    for state in ("IDLE", "ACQUIRING", "WAITING", "EDITING", "FINISHING", "PUBLISHED"):
        assert state in TX


def test_report_delivery_follows_verified_publication():
    assert "self._generate_reports(set(self._dirty_student_ids))" in TX
    assert TX.index("self._generate_reports(set(self._dirty_student_ids))") > TX.index("self._recovery_journal.published(")
    section = _section(MAIN, 'def on_publish_success()', 'def on_publish_failure')
    assert 'generate_student_report' not in section

def test_profile_image_change_marks_student_aggregate_dirty():
    section = _section(STUDENT, "def set_profile_image", "def update_student")
    assert "StudentUpdated(" in section
    assert 'changes=["profile_image_path"]' in section
    assert "student_id=student.id" in section


def test_parent_events_are_mapped_to_student_aggregate():
    section = _section(MAIN, "def _on_parent_event", "def _on_student_archived_event")
    assert "mark_student_dirty(student_id)" in section


def test_student_lifecycle_events_dirty_the_student():
    assert MAIN.count("mark_student_dirty(event.student_id)") >= 3


def test_snapshot_cleanup_happens_after_successful_publish_and_release():
    success = _section(TX, "def _publish(self)", "def _do_publish")
    success_branch = success[success.index("if success:"):success.index("else:")]
    assert "self._release_lock()" in success_branch
    assert "self._delete_snapshot()" in success_branch
    assert success_branch.index("self._delete_snapshot()") > success_branch.index("self._release_lock()")


def test_failed_publish_retains_recovery_snapshot():
    section = _section(TX, "def _publish(self)", "def _do_publish")
    failure = section[section.index("else:"):]
    assert "self._delete_snapshot()" not in failure


def test_forced_cancel_restores_before_cleanup():
    section = _section(TX, "def cancel_editing", "# ---- Publish helpers ----")
    assert "self._restore_snapshot()" in section
    assert "self._delete_snapshot()" in section
    assert section.index("self._restore_snapshot()") < section.index("self._delete_snapshot()")


def test_latest_report_policy_is_preserved():
    assert 'self.generate_student_report(student_id, report_type="latest",' in REPORT
    assert "return [local]" in REPORT

def test_filter_search_sort_share_one_filtered_base_without_parent_n_plus_one():
    section = _section(LIST, "def _filter_students", "def _populate_table")
    assert "base = self._filtered_base" in section
    assert "parent_phone" in section
    assert 'getattr(student, "parents", None)' in section
    assert "get_parents_for_student" not in section


def test_all_student_lifecycle_filters_are_supported():
    assert '"Active": "ACTIVE"' in LIST
    assert '"Archived": "ARCHIVED"' in LIST
    assert '"Deleted": "DELETED"' in LIST


def test_refresh_clears_stale_bulk_selection():
    section = _section(LIST, "def refresh", "def _apply_filters_and_sort")
    assert "self._selected_ids = []" in section
    assert "self._update_bulk_bar()" in section


def test_read_only_mode_does_not_advertise_mutation_actions():
    section = _section(LIST, "def _on_context_menu", "def _archive_student")
    assert "can_write = self._write_enabled or self.can_write()" in section
    assert section.count("setEnabled(can_write)") >= 3