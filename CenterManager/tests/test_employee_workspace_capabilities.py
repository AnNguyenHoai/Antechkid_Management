from pathlib import Path
from types import SimpleNamespace

from centermanager.models.permission import PermissionDefinitions
from centermanager.models.role import RoleDefinitions
from centermanager.ui.employee_workspace.employee_workspace_capabilities import (
    EmployeeWorkspaceCapabilities,
)


ROOT = Path(__file__).resolve().parent.parent
SHELL = (
    ROOT / "src" / "centermanager" / "ui" / "employee_workspace"
    / "employee_workspace_shell.py"
)


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


def test_management_mode_does_not_depend_on_registration_review_permission():
    permissions = FakePermissionService({PermissionDefinitions.EMPLOYEE_VIEW_ALL})
    caps = EmployeeWorkspaceCapabilities.resolve(permissions, user())

    assert caps.management is True
    assert caps.registration_all is False
    assert [item["id"] for item in caps.management_nav_items()] == ["employees"]


def test_self_navigation_only_exposes_granted_operational_capabilities():
    permissions = FakePermissionService({
        PermissionDefinitions.WORKING_TIME_VIEW_SELF,
        PermissionDefinitions.SCHEDULE_VIEW_SELF,
    })
    caps = EmployeeWorkspaceCapabilities.resolve(permissions, user())

    assert [item["id"] for item in caps.self_nav_items()] == [
        "profile", "attendance", "schedule"
    ]
    assert caps.registration_self is False


def test_self_registration_is_independent_from_schedule_and_attendance():
    permissions = FakePermissionService({PermissionDefinitions.WORK_REGISTRATION_SELF})
    caps = EmployeeWorkspaceCapabilities.resolve(permissions, user())

    assert [item["id"] for item in caps.self_nav_items()] == [
        "profile", "registration"
    ]


def test_shell_does_not_eagerly_resolve_employee_or_create_operational_pages():
    source = SHELL.read_text(encoding="utf-8")
    shell_start = source.index("class EmployeeWorkspaceShell")
    setup_start = source.index("    def _setup(self):", shell_start)
    setup_end = source.index("    def _ensure_management_list_page(self):", setup_start)
    setup = source[setup_start:setup_end]

    assert "get_current_employee(" not in setup
    assert "EmployeeListPage(" not in setup
    assert "EmployeeWorkRegistrationReviewPage(" not in setup
    assert "EmployeeWorkRegistrationWidget(" not in setup
    assert "self.self_page.refresh()" not in setup


def test_shell_lazy_loads_each_operational_page_on_navigation():
    source = SHELL.read_text(encoding="utf-8")

    assert "def _ensure_management_list_page(self):" in source
    assert "def _ensure_registration_review_page(self):" in source
    assert "def _ensure_management_self_registration(self):" in source
    assert "def _ensure_registration_page(self):" in source
    assert "def _ensure_attendance_page(self):" in source
    assert 'if page_id == "attendance":' in source
    assert 'if page_id == "registration":' in source
    assert 'if page_id == "schedule":' in source


def test_shell_uses_capability_policy_for_navigation():
    source = SHELL.read_text(encoding="utf-8")

    assert "EmployeeWorkspaceCapabilities.resolve" in source
    assert "self.capabilities.management_nav_items()" in source
    assert "self.capabilities.self_nav_items()" in source
    assert "self.capabilities.registration_all" in source
    assert "self.capabilities.attendance_self" in source
    assert "self.capabilities.schedule_self" in source
