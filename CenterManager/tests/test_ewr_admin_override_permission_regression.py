from pathlib import Path

SERVICE = (
    Path(__file__).resolve().parent.parent
    / "src" / "centermanager" / "services"
    / "employee_work_registration_service.py"
)


def test_admin_override_branch_is_explicit_and_bypasses_closed_period_gate():
    source = SERVICE.read_text(encoding="utf-8")
    assert "if admin_override:" in source
    assert 'if r.status!=EmployeeWorkRegistration.STATUS_DRAFT and not admin_override' in source
    assert '"admin_override":admin_override' in source


def test_get_period_checks_global_scope_before_employee_self_scope():
    source = SERVICE.read_text(encoding="utf-8")
    all_check = 'if self._permission_service.has_permission(self.ALL_PERMISSION, u):'
    self_check = 'if employee is not None and ('
    assert all_check in source
    assert self_check in source
    assert source.index(all_check) < source.index(self_check)
