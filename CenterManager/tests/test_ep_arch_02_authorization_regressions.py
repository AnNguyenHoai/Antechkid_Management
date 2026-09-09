from types import SimpleNamespace

import pytest

from centermanager.core.capabilities import Capability
from centermanager.models.permission import PermissionDefinitions
from centermanager.services.authorization_service import AuthorizationService, AuthorizationDecision


def principal(role="teacher", permissions=(), is_active=True):
    return SimpleNamespace(
        role=SimpleNamespace(name=role),
        permissions=set(permissions),
        is_active=is_active,
    )


def test_lightweight_principal_is_supported_without_orm_attributes():
    user = principal(permissions={Capability.EMPLOYEE_UPDATE_SELF.value})
    assert AuthorizationService.allows(user, Capability.EMPLOYEE_UPDATE_SELF)
    assert not AuthorizationService.allows(user, Capability.EMPLOYEE_VIEW_ALL)


def test_omitted_lifecycle_attribute_does_not_break_lightweight_principal():
    user = SimpleNamespace(
        role=SimpleNamespace(name="teacher"),
        permissions={Capability.SCHEDULE_VIEW_SELF.value},
    )
    assert AuthorizationService.allows(user, Capability.SCHEDULE_VIEW_SELF)


def test_admin_has_privileged_system_access_without_persisted_permission_rows():
    admin = principal(role="admin")
    assert AuthorizationService.decide(admin, Capability.SCHEDULE_MANAGE) is AuthorizationDecision.DENY
    assert AuthorizationService.decide(admin, Capability.EMPLOYEE_DELETE) is AuthorizationDecision.ALLOW


def test_manager_employee_management_compatibility_is_narrow_and_centralized():
    manager = principal(role="manager")
    assert AuthorizationService.allows(manager, Capability.EMPLOYEE_CREATE)
    assert AuthorizationService.allows(manager, Capability.EMPLOYEE_UPDATE)
    assert AuthorizationService.allows(manager, Capability.EMPLOYEE_ARCHIVE)
    assert not AuthorizationService.allows(manager, Capability.SCHEDULE_MANAGE)
    assert not AuthorizationService.allows(manager, Capability.EMPLOYEE_DELETE)


def test_broad_employee_update_implies_only_self_update():
    manager = principal(role="teacher", permissions={Capability.EMPLOYEE_UPDATE.value})
    assert AuthorizationService.allows(manager, Capability.EMPLOYEE_UPDATE_SELF)
    assert not AuthorizationService.allows(manager, Capability.SCHEDULE_MANAGE)


def test_legacy_registration_permission_is_read_as_canonical_capability():
    assert Capability.from_value("working_time.registration.self") is Capability.WORK_REGISTRATION_SELF
    teacher = principal(permissions={"working_time.registration.self"})
    assert AuthorizationService.allows(teacher, Capability.WORK_REGISTRATION_SELF)


def test_inactive_principal_is_denied():
    user = principal(permissions={Capability.EMPLOYEE_UPDATE_SELF.value}, is_active=False)
    assert AuthorizationService.decide(user, Capability.EMPLOYEE_UPDATE_SELF) is AuthorizationDecision.DENY
