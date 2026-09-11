"""Regression coverage for the working-time service repository boundary."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from centermanager.services.employee_working_time_service import EmployeeWorkingTimeService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = PROJECT_ROOT / "src" / "centermanager" / "services" / "employee_working_time_service.py"


def test_working_time_service_uses_injected_provider_for_employee_lookup_and_entries():
    session = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session

    provider = MagicMock()
    employee_repo = MagicMock()
    working_repo = MagicMock()
    employee = MagicMock(id=11, user_id=7)
    employee_repo.get_by_id.return_value = employee
    working_repo.list_for_employee.return_value = []
    provider.employees.return_value = employee_repo
    provider.employee_working_times.return_value = working_repo

    service = EmployeeWorkingTimeService(factory, repository_provider=provider)
    actor = MagicMock(id=7)

    with patch.object(service, "_has", return_value=True):
        result = service.list_entries(11, user=actor)

    assert result == []
    provider.employees.assert_called_once_with(session)
    employee_repo.get_by_id.assert_called_once_with(11)
    provider.employee_working_times.assert_called_once_with(session)
    working_repo.list_for_employee.assert_called_once_with(11, None, None)


def test_working_time_service_has_no_concrete_repository_imports_or_construction():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
    concrete_imports: list[str] = []
    concrete_constructors: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories.") and module != "centermanager.repositories.provider":
                concrete_imports.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("centermanager.repositories.") and alias.name != "centermanager.repositories.provider":
                    concrete_imports.append(alias.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
                concrete_constructors.append(node.func.id)
            elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Repository"):
                concrete_constructors.append(node.func.attr)

    assert concrete_imports == []
    assert concrete_constructors == []
