"""Regression coverage for the EmployeeService repository boundary."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from centermanager.services.employee_service import EmployeeService


SERVICES_DIR = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"


def test_employee_service_uses_injected_repository_provider_for_reads():
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session

    provider = MagicMock()
    repo = MagicMock()
    employee = MagicMock()
    repo.list_all.return_value = [employee]
    provider.employees.return_value = repo

    service = EmployeeService(session_factory, repository_provider=provider)
    actor = MagicMock(id=7)

    with patch.object(service, "can_view_all", return_value=True):
        result = service.list_visible_employees(actor)

    assert result == [employee]
    provider.employees.assert_called_once_with(session)
    repo.list_all.assert_called_once_with()


def test_employee_service_does_not_import_or_construct_concrete_repositories():
    path = SERVICES_DIR / "employee_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

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
