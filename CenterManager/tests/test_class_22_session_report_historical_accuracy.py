from pathlib import Path

SERVICE = Path("src/centermanager/services/session_report_service.py").read_text(encoding="utf-8")
GENERATOR = Path("src/centermanager/export/pdf/session_report_generator.py").read_text(encoding="utf-8")


def test_historical_teacher_is_resolved_from_session_teacher_id():
    assert "def _resolve_teacher_name" in SERVICE
    assert "session.teacher_id" in SERVICE
    assert "TeacherRepository" in SERVICE
    assert '"teacher_name": teacher_name' in SERVICE


def test_class_teacher_is_only_fallback():
    start = SERVICE.index("def _resolve_teacher_name")
    end = SERVICE.index("def get_output_path", start)
    block = SERVICE[start:end]
    assert block.index("session.teacher_id") < block.index('getattr(class_obj, "teachers"')


def test_generator_uses_resolved_teacher_name():
    assert 'teacher_name = data.get("teacher_name")' in GENERATOR
    assert '["Giáo viên", teacher_name]' in GENERATOR


def test_status_is_localized_to_vietnamese():
    for source, label in {
        "Scheduled": "Đã lên lịch",
        "Completed": "Hoàn thành",
        "Cancelled": "Đã hủy",
        "Postponed": "Hoãn",
    }.items():
        assert source in GENERATOR
        assert label in GENERATOR
    assert "localize_status(session.status)" in GENERATOR


def test_actual_and_scheduled_dates_are_both_shown_when_different():
    assert "session.actual_date != session.scheduled_date" in GENERATOR
    assert '"Ngày dự kiến"' in GENERATOR
    assert '"Ngày thực tế"' in GENERATOR
