from types import SimpleNamespace

import pytest

from centermanager.core.capabilities import (
    ADMIN_ONLY_CAPABILITIES,
    Capability,
    PERSISTED_CAPABILITIES,
)
from centermanager.models.permission import PermissionDefinitions
from centermanager.services.authorization_service import (
    AuthorizationDecision,
    AuthorizationService,
)
from centermanager.services.permission_service import PermissionDeniedError


def make_user(*permissions, role_name="employee", active=True):
    granted = set(permissions)
    role = SimpleNamespace(name=role_name)
    return SimpleNamespace(
        id=1,
        is_active=active,
        role=role,
        has_permission=lambda name: name in granted,
    )


def test_capability_registry_is_unique_and_round_trips():
    values = Capability.values()
    assert values
    assert len(values) == len(set(values))
    for value in values:
        assert Capability.from_value(value).value == value


def test_legacy_permission_definitions_are_aliases_of_canonical_registry():
    assert PermissionDefinitions.STUDENT_VIEW == Capability.STUDENT_VIEW.value
    assert PermissionDefinitions.WORK_REGISTRATION_VIEW_ALL == Capability.WORK_REGISTRATION_VIEW_ALL.value
    assert PermissionDefinitions.WORK_REGISTRATION_PERIOD_ADMIN_OVERRIDE == Capability.WORK_REGISTRATION_PERIOD_ADMIN_OVERRIDE.value
    assert PermissionDefinitions.EMPLOYEE_DELETE == Capability.EMPLOYEE_DELETE.value
    assert set(PermissionDefinitions.all_permissions()) == set(PERSISTED_CAPABILITIES)
    assert ADMIN_ONLY_CAPABILITIES.isdisjoint(PERSISTED_CAPABILITIES)


def test_admin_has_no_generic_capability_bypass():
    admin_without_delete = make_user(role_name="admin")
    assert AuthorizationService.decide(admin_without_delete, Capability.EMPLOYEE_UPDATE) is AuthorizationDecision.DENY


def test_admin_only_capability_is_explicitly_policy_controlled():
    admin = make_user(role_name="admin")
    manager = make_user(role_name="manager")
    employee = make_user(role_name="employee")

    for capability in ADMIN_ONLY_CAPABILITIES:
        assert AuthorizationService.allows(admin, capability)
        assert not AuthorizationService.allows(manager, capability)
        assert not AuthorizationService.allows(employee, capability)


def test_explicit_capability_grant_allows_operation():
    manager = make_user(Capability.CLASS_TEACHER_ASSIGNMENT_MANAGE.value, role_name="manager")
    assert AuthorizationService.allows(manager, Capability.CLASS_TEACHER_ASSIGNMENT_MANAGE)


def test_inactive_actor_is_denied_even_with_capability():
    user = make_user(Capability.STUDENT_VIEW.value, active=False)
    assert AuthorizationService.decide(user, Capability.STUDENT_VIEW) is AuthorizationDecision.DENY


def test_unknown_capability_fails_closed():
    user = make_user(role_name="admin")
    with pytest.raises(ValueError, match="Unknown capability"):
        AuthorizationService.allows(user, "not.a.real.capability")


def test_any_and_all_use_capability_decisions():
    user = make_user(
        Capability.STUDENT_VIEW.value,
        Capability.CLASS_VIEW.value,
    )
    assert AuthorizationService.allows_any(user, [Capability.STUDENT_VIEW, Capability.EMPLOYEE_DELETE])
    assert not AuthorizationService.allows_all(user, [Capability.STUDENT_VIEW, Capability.EMPLOYEE_DELETE])


def test_require_denies_without_mutating_actor():
    user = make_user(role_name="manager")
    with pytest.raises(PermissionDeniedError, match="Capability 'employee.delete' is required"):
        AuthorizationService.require(user, Capability.EMPLOYEE_DELETE)
