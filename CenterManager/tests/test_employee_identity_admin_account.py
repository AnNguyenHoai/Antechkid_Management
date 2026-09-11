from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeService,
    EmployeeValidationError,
)
from centermanager.services.permission_service import PermissionService


def _user(role_name: str):
    role = SimpleNamespace(name=role_name)
    return SimpleNamespace(
        id=99,
        full_name="System Administrator",
        phone=None,
        email=None,
        role=role,
    )


def test_admin_role_is_not_an_employee_identity():
    admin = _user(RoleDefinitions.ADMIN)
    teacher = _user(RoleDefinitions.TEACHER)

    assert EmployeeService._is_employee_account(admin) is False
    assert EmployeeService._is_employee_account(teacher) is True


def test_admin_cannot_acquire_employee_identity_via_current_employee_resolver():
    service = EmployeeService(Mock(side_effect=AssertionError("DB must not be touched")))

    with pytest.raises(EmployeeAccessDeniedError, match="do not have an employee identity"):
        service.get_current_employee(_user(RoleDefinitions.ADMIN))


def test_admin_cannot_acquire_employee_identity_via_legacy_resolver():
    service = EmployeeService(Mock(side_effect=AssertionError("DB must not be touched")))

    with pytest.raises(EmployeeAccessDeniedError, match="do not have an employee identity"):
        service.get_or_create_employee_for_user(_user(RoleDefinitions.ADMIN))


def test_permission_service_provisions_employee_only_for_non_admin_roles():
    assert PermissionService._should_provision_employee(RoleDefinitions.ADMIN) is False
    assert PermissionService._should_provision_employee(RoleDefinitions.TEACHER) is True
    assert PermissionService._should_provision_employee(RoleDefinitions.MANAGER) is True


def test_employee_account_creation_rejects_admin_role_before_database_work():
    manager = _user(RoleDefinitions.MANAGER)
    service = EmployeeService(Mock(side_effect=AssertionError("DB must not be touched")))

    with patch("centermanager.services.employee_service.get_current_user", return_value=manager):
        with pytest.raises(EmployeeValidationError, match="system identities and cannot be employees"):
            service.create_employee_with_account(
                "Administrator",
                "admin2",
                RoleDefinitions.ADMIN,
                temp_password="secret",
            )
