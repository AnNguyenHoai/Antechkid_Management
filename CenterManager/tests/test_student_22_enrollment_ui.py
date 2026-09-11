from pathlib import Path

WIDGET = Path("src/centermanager/ui/student_workspace/enrollment_widget.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/student_workspace/student_detail_page.py").read_text(encoding="utf-8")
SHELL = Path("src/centermanager/ui/student_workspace/student_workspace_shell.py").read_text(encoding="utf-8")
MAIN = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
APP = Path("src/centermanager/app.py").read_text(encoding="utf-8")

def test_enrollment_widget_has_current_and_history_surfaces():
    assert "Current Enrollment" in WIDGET
    assert "Academic History" in WIDGET
    assert "No active enrollment." in WIDGET

def test_enrollment_widget_supports_enroll_complete_withdraw():
    for api in ("._enrollment_service.enroll(", "._enrollment_service.complete(", "._enrollment_service.withdraw("):
        assert api in WIDGET

def test_enrollment_mutations_are_write_guarded():
    assert "set_write_enabled" in WIDGET
    assert "Start Editing before changing enrollment." in WIDGET

def test_detail_page_hosts_enrollment_tab_and_refreshes_student():
    assert "EnrollmentWidget" in DETAIL
    assert '"🎓 Enrollment"' in DETAIL
    assert "self.enrollment_widget.set_student(student.id)" in DETAIL

def test_enrollment_write_state_is_propagated():
    assert "self.enrollment_widget," in DETAIL

def test_service_is_wired_from_app_to_student_workspace():
    assert "EnrollmentService(session_factory, event_bus=event_bus)" in APP
    assert "enrollment_service=enrollment_service" in APP
    assert "enrollment_service=self._enrollment_service" in MAIN
    assert "enrollment_service=self._enrollment_service" in SHELL
