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


def test_admin_can_override_registration_status_and_closed_period_in_detail_service():
    source = (ROOT.parent.parent / "services" / "employee_work_registration_service.py").read_text(encoding="utf-8")
    assert 'ADMIN_OVERRIDE_PERMISSION="work_registration.period.admin_override"' in source
    assert 'def can_admin_override(self,user=None):' in source
    assert 'if r.status!=EmployeeWorkRegistration.STATUS_DRAFT and not admin_override' in source
    assert 'if admin_override:' in source
    assert '"admin_override":admin_override' in source


def test_employee_aggregate_cascades_employee_documents_on_hard_delete():
    source = (ROOT.parent.parent / "models" / "employee.py").read_text(encoding="utf-8")
    assert 'documents = relationship("EmployeeDocument", cascade="all, delete-orphan")' in source


def test_teacher_role_receives_own_work_registration_permission():
    source = (ROOT.parent.parent / "database" / "seed.py").read_text(encoding="utf-8")
    assert 'PermissionDefinitions.WORK_REGISTRATION_SELF,' in source


def test_existing_databases_receive_teacher_work_registration_permission():
    """The canonical runtime repair migration grants teachers the self permission."""
    migration = (
        ROOT.parent.parent.parent.parent
        / "migrations" / "versions" / "1e10a016_runtime_employee_registration_repairs.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "1e10a016"' in migration
    assert 'down_revision = "1e10a015"' in migration
    assert 'SELF_PERMISSION = "work_registration.self"' in migration
    assert 'INSERT OR IGNORE INTO role_permissions' in migration
    assert 'TEACHER_ROLE = "teacher"' in migration
