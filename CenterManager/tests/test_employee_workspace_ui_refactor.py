
from pathlib import Path

PROFILE = Path("src/centermanager/ui/employee_workspace/employee_list_page.py").read_text(encoding="utf-8")
SCHEDULE = Path("src/centermanager/ui/employee_workspace/employee_schedule_widget.py").read_text(encoding="utf-8")
WORKING = Path("src/centermanager/ui/employee_workspace/employee_working_time_widget.py").read_text(encoding="utf-8")


def test_management_profile_is_tabbed_and_embedded():
    assert 'self.tabs = QTabWidget()' in PROFILE
    assert 'self.tabs.addTab(page, "Overview")' in PROFILE
    assert 'self.tabs.addTab(page, "Schedule")' in PROFILE
    assert 'self.tabs.addTab(page, "Attendance")' in PROFILE
    assert 'self.tabs.addTab(page, "Documents")' in PROFILE
    assert 'self.setWindowFlags(Qt.WindowType.Widget)' in PROFILE


def test_profile_has_explicit_in_window_back_navigation():
    assert 'self.back_btn = QPushButton("← Employees")' in PROFILE
    assert 'self.back_requested.emit' in PROFILE


def test_schedule_tables_have_usable_minimum_height():
    assert 'self.rules.setMinimumHeight(190)' in SCHEDULE
    assert 'self.exceptions.setMinimumHeight(150)' in SCHEDULE
    assert 'QHeaderView.ResizeMode.Stretch' in SCHEDULE


def test_working_time_table_has_usable_height_and_self_mode_controls():
    assert 'self.table.setMinimumHeight(260)' in WORKING
    assert 'if self.management:' in WORKING
    assert 'self.add' in WORKING
    assert 'self.edit' in WORKING
    assert 'self.delete' in WORKING
