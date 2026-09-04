from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "src" / "centermanager" / "ui" / "employee_workspace" / "employee_workspace_shell.py"


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
    assert 'Permission denied for Work Registration' in source


def test_work_registration_service_uses_canonical_self_and_all_permissions():
    service = (ROOT / "src" / "centermanager" / "services" / "employee_work_registration_service.py").read_text(encoding="utf-8")
    assert 'SELF_PERMISSION="work_registration.self"' in service
    assert 'ALL_PERMISSION="work_registration.view.all"' in service
