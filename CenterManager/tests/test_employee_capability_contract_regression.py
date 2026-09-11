from types import SimpleNamespace

from centermanager.models.permission import PermissionDefinitions
from centermanager.services.employee_capability_policy import EmployeeCapabilityPolicy
from centermanager.ui.employee_workspace.employee_workspace_capabilities import (
    EmployeeWorkspaceCapabilities,
)


class FakeUser:
    def __init__(self, *permissions, role_name="TEACHER"):
        self.id = 1
        self.role = SimpleNamespace(name=role_name)
        self._permissions = set(permissions)

    def has_permission(self, permission):
        return permission in self._permissions


def test_broad_employee_update_is_a_valid_self_update_capability():
    user = FakeUser(PermissionDefinitions.EMPLOYEE_UPDATE)

    assert EmployeeCapabilityPolicy.has(
        user, PermissionDefinitions.EMPLOYEE_UPDATE_SELF
    )


def test_view_self_never_grants_update_self():
    user = FakeUser(PermissionDefinitions.EMPLOYEE_VIEW_SELF)

    assert EmployeeCapabilityPolicy.has(
        user, PermissionDefinitions.EMPLOYEE_VIEW_SELF
    )
    assert not EmployeeCapabilityPolicy.has(
        user, PermissionDefinitions.EMPLOYEE_UPDATE_SELF
    )


def test_workspace_capability_public_aliases_match_resolved_contract():
    user = FakeUser(PermissionDefinitions.EMPLOYEE_VIEW_SELF)

    class PermissionServiceStub:
        def has_permission(self, permission, _user):
            return permission in user._permissions

        def is_admin(self, _user):
            return False

        def has_any_permission(self, permissions, _user):
            return any(permission in user._permissions for permission in permissions)

    caps = EmployeeWorkspaceCapabilities.resolve(PermissionServiceStub(), user)

    assert caps.can_view_self
    assert not caps.can_update_self
    assert not caps.can_update_all
