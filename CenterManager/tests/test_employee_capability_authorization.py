from pathlib import Path
from types import SimpleNamespace

from centermanager.models.permission import PermissionDefinitions
from centermanager.models.role import RoleDefinitions
from centermanager.ui.employee_workspace.employee_workspace_capabilities import (
    EmployeeWorkspaceCapabilities,
)


ROOT = Path(__file__).resolve().parent.parent
SERVICE = ROOT / "src" / "centermanager" / "services" / "employee_service.py"


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


def test_view_self_never_grants_update_self():
    caps = EmployeeWorkspaceCapabilities.resolve(
        FakePermissionService({PermissionDefinitions.EMPLOYEE_VIEW_SELF}), user()
    )
    assert caps.employee_profile_self
    assert not caps.employee_update_self
    assert not caps.can_edit_profile(True)


def test_update_self_is_explicit():
    caps = EmployeeWorkspaceCapabilities.resolve(
        FakePermissionService({
            PermissionDefinitions.EMPLOYEE_VIEW_SELF,
            PermissionDefinitions.EMPLOYEE_UPDATE_SELF,
        }),
        user(),
    )
    assert caps.can_edit_profile(True)
    assert not caps.can_edit_profile(False)


def test_update_all_is_independent_from_view_all():
    caps = EmployeeWorkspaceCapabilities.resolve(
        FakePermissionService({PermissionDefinitions.EMPLOYEE_VIEW_ALL}), user()
    )
    assert caps.employee_view_all
    assert not caps.employee_update_all
    assert not caps.can_edit_profile(False)


def test_working_time_read_does_not_grant_write():
    caps = EmployeeWorkspaceCapabilities.resolve(
        FakePermissionService({PermissionDefinitions.WORKING_TIME_VIEW_SELF}), user()
    )
    assert caps.attendance_self
    assert not caps.attendance_create_self
    assert not caps.attendance_manage


def test_schedule_read_does_not_grant_manage():
    caps = EmployeeWorkspaceCapabilities.resolve(
        FakePermissionService({
            PermissionDefinitions.SCHEDULE_VIEW_SELF,
            PermissionDefinitions.SCHEDULE_VIEW_ALL,
        }),
        user(),
    )
    assert caps.schedule_self
    assert caps.schedule_all
    assert not caps.schedule_manage


def test_registration_review_does_not_grant_manage():
    caps = EmployeeWorkspaceCapabilities.resolve(
        FakePermissionService({PermissionDefinitions.WORK_REGISTRATION_VIEW_ALL}), user()
    )
    assert caps.registration_all
    assert not caps.registration_manage


def test_employee_service_does_not_use_view_self_as_update_fallback():
    source = SERVICE.read_text(encoding="utf-8")
    forbidden = '''actor.has_permission("employee.update.self")\n                    or actor.has_permission("employee.view.self")'''
    assert forbidden not in source
    assert 'if not actor.has_permission("employee.update.self"):' in source
