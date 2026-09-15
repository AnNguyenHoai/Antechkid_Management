import pytest

from centermanager.models.employee import Employee
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeService,
    EmployeeValidationError,
)


class _Role:
    def __init__(self, name):
        self.name = name


class _User:
    def __init__(self, role_name):
        self.role = _Role(role_name)


def test_validate_status_accepts_all_canonical_employee_statuses():
    for status in Employee.VALID_STATUSES:
        assert EmployeeService._validate_status(status.lower()) == status


def test_validate_status_rejects_unknown_status():
    with pytest.raises(EmployeeValidationError, match="Invalid employment status"):
        EmployeeService._validate_status("NOT_A_REAL_STATUS")


def test_admin_is_not_an_employee_account():
    assert EmployeeService._is_employee_account(_User(RoleDefinitions.ADMIN)) is False


def test_employee_roles_may_own_employee_identity():
    for role_name in (
        RoleDefinitions.TEACHER,
        RoleDefinitions.MANAGER,
        RoleDefinitions.RECEPTION,
        RoleDefinitions.FINANCE,
    ):
        assert EmployeeService._is_employee_account(_User(role_name)) is True


def test_admin_current_employee_resolution_is_denied_before_database_access():
    class _FailIfOpened:
        def __call__(self):
            raise AssertionError("Admin identity check must not open an employee DB session")

    service = EmployeeService(_FailIfOpened())
    with pytest.raises(EmployeeAccessDeniedError, match="do not have an employee identity"):
        service.get_current_employee(_User(RoleDefinitions.ADMIN))
