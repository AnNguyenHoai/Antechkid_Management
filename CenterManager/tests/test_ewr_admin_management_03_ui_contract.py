from pathlib import Path


ROOT = Path("src/centermanager/ui/employee_workspace")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_employee_workspace_exposes_admin_employee_delete_action():
    source = read("employee_list_page.py")
    assert 'QInputDialog' in source
    assert 'self.delete_btn = QPushButton("Delete Employee")' in source
    assert 'self.table.selection_changed.connect(self._on_selection_changed)' in source
    assert 'def delete_selected(self):' in source
    assert 'self._admin_service.delete_employee(employee_id, reason=reason.strip())' in source


def test_registration_review_exposes_admin_closed_period_reopen_action():
    source = read("employee_work_registration_review_page.py")
    assert 'self.reopen_period_btn = QPushButton("Re-open Closed Month")' in source
    assert 'def reopen_period(self):' in source
    assert 'self._admin_service.reopen_period(year, month, reason=reason)' in source
    assert 'Registration workflow states will not be changed.' in source


def test_registration_detail_exposes_edit_delete_only_for_open_draft():
    source = read("employee_work_registration_detail_page.py")
    assert 'self.edit_btn = QPushButton("Edit Selected")' in source
    assert 'self.delete_btn = QPushButton("Delete Selected")' in source
    assert 'r.status == EmployeeWorkRegistration.STATUS_DRAFT' in source
    assert 'self._period_status != EmployeeWorkRegistrationPeriod.STATUS_CLOSED' in source
