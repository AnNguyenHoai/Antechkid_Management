from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_admin_management_service import (
    EmployeeAdminManagementAccessDeniedError,
    EmployeeAdminManagementService,
    EmployeeAdminManagementValidationError,
)


ROOT = Path("src/centermanager")


def _service():
    return EmployeeAdminManagementService(lambda: None)


def _user(role_name):
    return SimpleNamespace(id=7, username="actor", role=SimpleNamespace(name=role_name))


def test_admin_management_is_explicitly_admin_only():
    service = _service()

    assert service._require_admin(_user(RoleDefinitions.ADMIN)).id == 7
    with pytest.raises(EmployeeAdminManagementAccessDeniedError):
        service._require_admin(_user(RoleDefinitions.MANAGER))
    with pytest.raises(EmployeeAdminManagementAccessDeniedError):
        service._require_admin(_user(RoleDefinitions.TEACHER))


def test_admin_override_and_delete_capabilities_are_stable():
    service = _service()

    assert service.CAPABILITY_PERIOD_OVERRIDE == "work_registration.period.admin_override"
    assert service.CAPABILITY_REGISTRATION_DELETE == "work_registration.delete"
    assert service.CAPABILITY_EMPLOYEE_DELETE == "employee.delete"
    assert service.ACTION_PERIOD_REOPENED == "WORK_REGISTRATION_PERIOD_ADMIN_REOPENED"
    assert service.ACTION_REGISTRATION_DELETED == "WORK_REGISTRATION_ADMIN_DELETED"
    assert service.ACTION_EMPLOYEE_DELETED == "EMPLOYEE_ADMIN_DELETED"


def test_admin_reopen_requires_a_reason_before_touching_storage():
    service = _service()

    with pytest.raises(EmployeeAdminManagementValidationError, match="reason is required"):
        service.reopen_period(2026, 10, user=_user(RoleDefinitions.ADMIN))


def test_admin_delete_registration_requires_a_reason_before_touching_storage():
    service = _service()

    with pytest.raises(EmployeeAdminManagementValidationError, match="reason is required"):
        service.delete_registration(123, user=_user(RoleDefinitions.ADMIN))


def test_admin_delete_employee_requires_a_reason_before_touching_storage():
    service = _service()

    with pytest.raises(EmployeeAdminManagementValidationError, match="reason is required"):
        service.delete_employee(123, user=_user(RoleDefinitions.ADMIN))


def test_admin_management_contract_is_separate_from_employee_self_service():
    source = (ROOT / "services" / "employee_admin_management_service.py").read_text(encoding="utf-8")
    assert "class EmployeeAdminManagementService" in source
    assert "def _require_admin" in source
    assert "def reopen_period" in source
    assert "def delete_registration" in source
    assert "def delete_employee" in source
    assert "WORK_REGISTRATION_PERIOD_ADMIN_REOPENED" in source
    assert "WORK_REGISTRATION_ADMIN_DELETED" in source
    assert "EMPLOYEE_ADMIN_DELETED" in source


def test_admin_employee_delete_is_blocked_when_operational_history_exists():
    source = (ROOT / "services" / "employee_admin_management_service.py").read_text(encoding="utf-8")
    assert '"work_registrations": len(employee.work_registrations)' in source
    assert '"schedule_rules": len(employee.schedule_rules)' in source
    assert '"schedule_exceptions": len(employee.schedule_exceptions)' in source
    assert '"working_time_entries": len(employee.working_time_entries)' in source
    assert "Archive the employee instead." in source
