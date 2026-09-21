from pathlib import Path

ATTENDANCE = Path("src/centermanager/services/attendance_service.py").read_text(encoding="utf-8")
AUTO = Path("src/centermanager/services/auto_report_service.py").read_text(encoding="utf-8")
REPORT = Path("src/centermanager/services/report_service.py").read_text(encoding="utf-8")


def test_attendance_defers_generation_to_publish_lifecycle():
    legacy_start = ATTENDANCE.index("def create_or_update_attendance")
    legacy_end = ATTENDANCE.index("\n    def _trigger_report_policy", legacy_start)
    legacy_body = ATTENDANCE[legacy_start:legacy_end]
    assert "_save_session_attendance_atomic(" in legacy_body

    atomic_start = ATTENDANCE.index("def _save_session_attendance_atomic")
    atomic_end = ATTENDANCE.index(
        '\n    @require_permission("attendance.create")\n    def save_session_attendance',
        atomic_start,
    )
    atomic_body = ATTENDANCE[atomic_start:atomic_end]
    assert "session.commit()" in atomic_body
    assert "_publish_session_save_side_effects(session_id, side_effects)" in atomic_body
    assert atomic_body.index("session.commit()") < atomic_body.index(
        "_publish_session_save_side_effects(session_id, side_effects)"
    )

    side_effect_start = ATTENDANCE.index("def _publish_session_save_side_effects")
    side_effect_end = ATTENDANCE.index(
        "\n    def _save_session_attendance_atomic",
        side_effect_start,
    )
    side_effect_body = ATTENDANCE[side_effect_start:side_effect_end]
    assert "StudentUpdated(" in side_effect_body
    assert "generate_student_report(" not in side_effect_body


def test_daily_auto_report_is_date_aware_and_retry_safe():
    assert "report_exists_on_date" in AUTO
    assert "completion state was not advanced" in AUTO
    assert 'and self._report_service.report_exists(student.id, "daily")' not in AUTO


def test_report_service_has_date_aware_contract():
    assert "def report_exists_on_date" in REPORT
