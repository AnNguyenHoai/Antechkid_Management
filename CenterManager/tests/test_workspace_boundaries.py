from types import SimpleNamespace

from centermanager.core.capabilities import Capability
from centermanager.services.employee_service import EmployeeService


def principal(role, permissions=()):
    return SimpleNamespace(
        role=SimpleNamespace(name=role),
        permissions=set(permissions),
        is_active=True,
    )


def test_admin_can_access_employee_workspace_and_view_all_employees():
    admin = principal("admin")
    service = EmployeeService(None)

    assert service.can_access_workspace(admin)
    assert service.can_view_all(admin)


def test_manager_can_access_employee_workspace_and_view_all_employees():
    manager = principal("manager")
    service = EmployeeService(None)

    assert service.can_access_workspace(manager)
    assert service.can_view_all(manager)


def test_regular_employee_requires_employee_self_view_capability():
    employee = principal("teacher")
    service = EmployeeService(None)

    assert not service.can_access_workspace(employee)

    employee.permissions.add(Capability.EMPLOYEE_VIEW_SELF.value)
    assert service.can_access_workspace(employee)
    assert not service.can_view_all(employee)


def test_admin_workspace_source_has_no_employee_work_registration_page():
    from pathlib import Path

    source = Path(__file__).parents[1] / "src" / "centermanager" / "ui" / "admin_workspace" / "admin_workspace_shell.py"
    text = source.read_text(encoding="utf-8")

    assert "AdminEmployeeWorkDataPage" not in text
    assert '"employee_work_data"' not in text
    assert "Employees & Work" not in text
