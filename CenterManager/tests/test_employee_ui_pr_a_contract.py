from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "centermanager" / "ui" / "employee_workspace"


def _source(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def test_employee_schedule_uses_focused_tabs_instead_of_stacked_sections():
    source = _source("employee_schedule_widget.py")
    assert "QTabWidget" in source
    assert 'addTab(self._build_week_tab(), "Week")' in source
    assert 'addTab(self._build_template_tab(), "Template")' in source
    assert 'addTab(self._build_exception_tab(), "Exceptions")' in source
    assert "self.planning_actions.setVisible(self.editable)" in source
    assert "self.rule_actions.setVisible(self.editable)" in source
    assert "self.exception_actions.setVisible(self.editable)" in source


def test_employee_operational_tables_share_one_layout_contract():
    expected = {
        "employee_schedule_widget.py",
        "employee_working_time_widget.py",
        "employee_work_registration_widget.py",
        "employee_work_registration_review_page.py",
        "employee_work_registration_detail_page.py",
    }
    for name in expected:
        source = _source(name)
        assert "configure_employee_table" in source, name
        assert "set_employee_row" in source, name


def test_employee_table_contract_avoids_refresh_time_width_jitter():
    table_source = _source("table_layout.py")
    working_time_source = _source("employee_working_time_widget.py")
    assert 'mode: str = "fixed"' in table_source
    assert 'spec.mode == "stretch"' in table_source
    assert "setTextElideMode" in table_source
    assert "setToolTip" in table_source
    assert "resizeColumnsToContents()" not in working_time_source


def test_employee_table_semantics_define_center_right_and_stretch_columns():
    schedule = _source("employee_schedule_widget.py")
    working_time = _source("employee_working_time_widget.py")
    registration = _source("employee_work_registration_widget.py")
    assert 'EmployeeTableColumn("stretch", None, LEFT)' in schedule
    assert 'EmployeeTableColumn("fixed", 78, RIGHT)' in working_time
    assert 'EmployeeTableColumn("fixed", 78, RIGHT)' in registration
