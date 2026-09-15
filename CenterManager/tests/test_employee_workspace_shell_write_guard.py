from pathlib import Path


SHELL = Path("src/centermanager/ui/employee_workspace/employee_workspace_shell.py")


def test_attendance_write_guard_only_targets_real_widget():
    source = SHELL.read_text(encoding="utf-8")
    assert "self.attendance_page.set_editable(self._write_enabled)" not in source
    assert "self._attendance_widget.set_editable(self._write_enabled)" in source
    assert "self._attendance_widget is not None" in source


def test_attendance_widget_is_created_with_current_write_state():
    source = SHELL.read_text(encoding="utf-8")
    assert "editable=self._write_enabled" in source
