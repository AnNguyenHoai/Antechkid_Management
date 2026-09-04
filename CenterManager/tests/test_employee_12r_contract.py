from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_employee_access_migration_adds_self_update_permission():
    p = ROOT / "migrations" / "versions" / "1e10a005_employee_profile_self_update.py"
    source = p.read_text(encoding="utf-8")
    assert 'revision = "1e10a005"' in source
    assert 'SELF_UPDATE = "employee.update.self"' in source
    assert "INSERT OR IGNORE INTO permissions" in source


def test_account_provisioning_excludes_admin_employee_identity():
    """Account provisioning must keep admin accounts separate from Employee."""
    p = ROOT / "src" / "centermanager" / "services" / "permission_service.py"
    source = p.read_text(encoding="utf-8")
    assert "Only employee roles receive an Employee identity; admin is account-only." in source
    assert "if self._should_provision_employee(role_name):" in source
    assert 'return role_name != RoleDefinitions.ADMIN' in source


def test_user_delete_does_not_orphan_employee():
    p = ROOT / "src" / "centermanager" / "services" / "permission_service.py"
    source = p.read_text(encoding="utf-8")
    assert "linked_employee = session.query(Employee).filter(Employee.user_id == user_id).first()" in source
    assert "Deactivate the account instead of deleting it." in source
