from pathlib import Path
from types import SimpleNamespace

from centermanager.models.permission import PermissionDefinitions
from centermanager.models.role import RoleDefinitions
from centermanager.ui.employee_workspace.employee_workspace_capabilities import (
    EmployeeWorkspaceCapabilities,
)


ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "src" / "centermanager" / "ui" / "employee_workspace" / "employee_workspace_shell.py"
CAPABILITIES = ROOT / "src" / "centermanager" / "ui" / "employee_workspace" / "employee_workspace_capabilities.py"
SERVICE = ROOT / "src" / "centermanager" / "services" / "employee_work_registration_service.py"


class FakePermissionService:
    def __init__(self, permissions=()):
        self.permissions = set(permissions)

    def has_permission(self, permission_name, user=None):
        return permission_name in self.permissions

    def has_any_permission(self, permission_names, user=None):
        return bool(self.permissions.intersection(permission_names))

    def is_admin(self, user=None):
        return bool(user and user.role and user.role.name == RoleDefinitions.ADMIN)


def user(role=RoleDefinitions.TEACHER):
    return SimpleNamespace(role=SimpleNamespace(name=role))


def test_employee_workspace_management_is_independent_from_registration_review_capability():
    permissions = FakePermissionService({PermissionDefinitions.EMPLOYEE_VIEW_ALL})
    caps = EmployeeWorkspaceCapabilities.resolve(permissions, user())

    assert caps.management is True
    assert caps.registration_all is False
    assert [item["id"] for item in caps.management_nav_items()] == ["employees"]


def test_employee_workspace_management_exposes_all_scope_registration_without_self_duplicate():
    permissions = FakePermissionService({
        PermissionDefinitions.EMPLOYEE_VIEW_ALL,
        PermissionDefinitions.WORK_REGISTRATION_VIEW_ALL,
        PermissionDefinitions.WORK_REGISTRATION_SELF,
    })
    caps = EmployeeWorkspaceCapabilities.resolve(permissions, user())

    assert caps.registration_all is True
    assert caps.registration_self is True
    assert [item["id"] for item in caps.management_nav_items()] == [
        "employees", "registrations"
    ]
    assert "my_registration" not in [item["id"] for item in caps.management_nav_items()]


def test_employee_workspace_self_registration_remains_independent_when_all_scope_is_absent():
    permissions = FakePermissionService({
        PermissionDefinitions.EMPLOYEE_VIEW_ALL,
        PermissionDefinitions.WORK_REGISTRATION_SELF,
    })
    caps = EmployeeWorkspaceCapabilities.resolve(permissions, user())

    assert caps.registration_all is False
    assert caps.registration_self is True
    assert [item["id"] for item in caps.management_nav_items()] == [
        "employees", "my_registration"
    ]


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


def test_shell_uses_capability_policy_for_registration_navigation():
    source = SHELL.read_text(encoding="utf-8")

    assert "EmployeeWorkspaceCapabilities.resolve" in source
    assert "self.capabilities.management_nav_items()" in source
    assert "self.capabilities.self_nav_items()" in source
    assert "self.capabilities.registration_all" in source
    assert "self.capabilities.registration_self" in source


def test_capability_policy_is_the_canonical_registration_navigation_boundary():
    source = CAPABILITIES.read_text(encoding="utf-8")

    assert "registration_self" in source
    assert "registration_all" in source
    assert "if self.registration_all:" in source
    assert "elif self.registration_self:" in source
