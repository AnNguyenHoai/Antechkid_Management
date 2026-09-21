from pathlib import Path
from types import SimpleNamespace

from centermanager.models.session import SessionStatus
from centermanager.services.attendance_service import AttendanceService


ROOT = Path(__file__).resolve().parents[1]
ATTENDANCE = (ROOT / "src/centermanager/services/attendance_service.py").read_text(encoding="utf-8")
SESSION = (ROOT / "src/centermanager/services/session_service.py").read_text(encoding="utf-8")
ATTENDANCE_UI = (ROOT / "src/centermanager/ui/session/session_attendance_widget.py").read_text(encoding="utf-8")


def test_prod_01_changed_sources_compile():
    compile(ATTENDANCE, "attendance_service.py", "exec")
    compile(SESSION, "session_service.py", "exec")
    compile(ATTENDANCE_UI, "session_attendance_widget.py", "exec")


def test_attendance_lifecycle_allows_scheduled_and_completed_only():
    assert AttendanceService._session_allows_attendance_write(
        SimpleNamespace(status=SessionStatus.SCHEDULED.value)
    )
    assert AttendanceService._session_allows_attendance_write(
        SimpleNamespace(status=SessionStatus.COMPLETED.value)
    )
    assert not AttendanceService._session_allows_attendance_write(
        SimpleNamespace(status=SessionStatus.CANCELLED.value)
    )
    assert not AttendanceService._session_allows_attendance_write(
        SimpleNamespace(status=SessionStatus.POSTPONED.value)
    )


def test_atomic_attendance_boundary_enforces_session_lifecycle_before_mutation():
    start = ATTENDANCE.index("def _save_session_attendance_atomic")
    end = ATTENDANCE.index("\n    @require_permission(\"attendance.create\")\n    def save_session_attendance", start)
    body = ATTENDANCE[start:end]

    require_pos = body.index("self._require_attendance_writeable(session_obj)")
    existing_load_pos = body.index("existing_by_student =")
    commit_pos = body.index("session.commit()")

    assert require_pos < existing_load_pos < commit_pos
    assert "SessionStatus.SCHEDULED.value" in ATTENDANCE
    assert "SessionStatus.COMPLETED.value" in ATTENDANCE


def test_attendance_updates_dirty_student_only_when_row_really_changes():
    side_effect_start = ATTENDANCE.index("def _publish_session_save_side_effects")
    save_start = ATTENDANCE.index("def _save_session_attendance_atomic")
    side_effect_body = ATTENDANCE[side_effect_start:save_start]

    assert "row_changed" in side_effect_body
    assert "if row_changed:" in side_effect_body
    assert "self._publish_student_attendance_updated(student_id)" in side_effect_body

    save_end = ATTENDANCE.index("\n    @require_permission(\"attendance.create\")\n    def save_session_attendance", save_start)
    save_body = ATTENDANCE[save_start:save_end]
    assert "existing.arrival_time != new_arrival_time" in save_body
    assert "existing.teacher_note != new_teacher_note" in save_body
    assert "side_effects.append((student_id, None, row[\"status\"], True))" in save_body


def test_student_updated_remains_post_commit_and_covers_existing_attendance_changes():
    save_start = ATTENDANCE.index("def _save_session_attendance_atomic")
    save_end = ATTENDANCE.index("\n    @require_permission(\"attendance.create\")\n    def save_session_attendance", save_start)
    save_body = ATTENDANCE[save_start:save_end]

    assert save_body.index("session.commit()") < save_body.index(
        "self._publish_session_save_side_effects(session_id, side_effects)"
    )
    assert "StudentUpdated(" in ATTENDANCE
    assert "generate_student_report(" not in ATTENDANCE


def test_attendance_ui_projects_lifecycle_and_collaboration_write_authority():
    assert "self._session_lifecycle_allows_write = False" in ATTENDANCE_UI
    assert "self._attendance_service.can_edit_session_attendance(session_id)" in ATTENDANCE_UI

    can_write_start = ATTENDANCE_UI.index("def _can_write")
    can_write_end = ATTENDANCE_UI.index("\n    def _apply_write_state", can_write_start)
    can_write_body = ATTENDANCE_UI[can_write_start:can_write_end]
    assert "if not self._session_lifecycle_allows_write:" in can_write_body
    assert "self._write_guard" in can_write_body

    save_start = ATTENDANCE_UI.index("def _save_attendance")
    save_end = ATTENDANCE_UI.index("\n    def refresh", save_start)
    assert "if not self._can_write():" in ATTENDANCE_UI[save_start:save_end]


def test_cancel_session_publishes_class_session_changed_after_commit():
    start = SESSION.index("def cancel_session")
    end = SESSION.index("\n    @require_permission(\"lesson.delete\")", start)
    body = SESSION[start:end]

    assert 'self._publish_class_session_changed(session_obj, action="cancelled")' in body
    assert body.index("db_session.commit()") < body.index(
        'self._publish_class_session_changed(session_obj, action="cancelled")'
    )
