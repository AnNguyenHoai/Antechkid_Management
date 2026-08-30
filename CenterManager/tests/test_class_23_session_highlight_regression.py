from pathlib import Path

WIDGET = Path("src/centermanager/ui/session/student_highlight_widget.py").read_text(encoding="utf-8")
DIALOG = Path("src/centermanager/ui/session/session_detail_dialog.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/session_report_service.py").read_text(encoding="utf-8")
GENERATOR = Path("src/centermanager/export/pdf/session_report_generator.py").read_text(encoding="utf-8")


def test_highlight_dropdown_is_scoped_to_session_class():
    assert "get_enrolled_students(session.class_id)" in WIDGET
    assert "list_students()" not in WIDGET


def test_highlight_widget_receives_class_and_session_services():
    assert "class_service: ClassService" in WIDGET
    assert "session_service: SessionService" in WIDGET
    assert "self._class_service" in WIDGET
    assert "self._session_service" in WIDGET


def test_dialog_passes_services_needed_for_class_scoped_highlights():
    assert "self._class_service," in DIALOG
    assert "self._session_service," in DIALOG


def test_session_report_loads_and_passes_highlights():
    assert "StudentHighlightService" in SERVICE
    assert "get_highlights_for_session(session_id)" in SERVICE
    assert '"highlights": highlights' in SERVICE


def test_session_pdf_renders_student_highlights():
    assert 'data.get("highlights")' in GENERATOR
    assert "ĐIỂM NỔI BẬT HỌC SINH" in GENERATOR
    assert 'getattr(item, "student", None)' in GENERATOR
