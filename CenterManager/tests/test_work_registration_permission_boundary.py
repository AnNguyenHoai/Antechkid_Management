from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "src" / "centermanager" / "ui" / "employee_workspace" / "employee_workspace_shell.py"
SERVICE = ROOT / "src" / "centermanager" / "services" / "employee_work_registration_service.py"


def test_employee_workspace_checks_registration_all_capability_before_management_review_ui():
    source = SHELL.read_text(encoding="utf-8")
    assert 'def _can_view_all_registrations(self, user):' in source
    assert '"work_registration.view.all"' in source
    assert 'self.management_mode = self._es.can_view_all(user) and self._can_view_all_registrations(user)' in source


def test_employee_workspace_does_not_construct_self_registration_without_self_capability():
    source = SHELL.read_text(encoding="utf-8")
    assert 'def _can_view_self_registration(self, user):' in source
    assert '"work_registration.self"' in source
    assert 'if management_employee and self._can_view_self_registration(user):' in source
    assert 'if can_self_registration:' in source


def test_employee_workspace_rechecks_self_registration_capability_on_navigation():
    source = SHELL.read_text(encoding="utf-8")
    assert 'if not self._can_view_self_registration(get_current_user()):' in source
    assert 'self.header.set_context("Employee Workspace", "My Profile")' in source


def test_work_registration_service_uses_canonical_self_and_all_permissions():
    source = SERVICE.read_text(encoding="utf-8")
    assert 'SELF_PERMISSION="work_registration.self"' in source
    assert 'ALL_PERMISSION="work_registration.view.all"' in source
    assert 'LEGACY_SELF_PERMISSION="working_time.registration.self"' in source


def test_get_period_checks_all_scope_before_employee_self_scope():
    source = SERVICE.read_text(encoding="utf-8")
    all_check = 'if self._permission_service.has_permission(self.ALL_PERMISSION, u):'
    self_check = 'if employee is not None and ('
    assert all_check in source
    assert self_check in source
    assert source.index(all_check) < source.index(self_check)
    assert 'return self._period_readonly(y, m)' in source
