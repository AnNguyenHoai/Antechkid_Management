from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_student_detail_context_uses_profile_and_enrollment_timeline():
    source = _read("src/centermanager/ui/student_workspace/student_detail_page.py")
    assert "self.tab_widget.addTab(self.profile_tab, \"Profile\")" in source
    assert 'self.tab_widget.addTab(self.enrollment_widget, "🎓 Enrollment")' in source
    assert 'self.timeline_section = self._create_vertical_section("📅 Timeline")' in source


def test_student_detail_back_navigation_uses_students_route():
    source = _read("src/centermanager/ui/student_workspace/student_workspace_shell.py")
    assert 'self.navigate_to("students")' in source
    assert "self.go_to_finance.emit()" in source
