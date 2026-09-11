"""Regression coverage for the EmployeeWorkRegistrationService repository boundary."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService


SERVICES_DIR = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"


def test_ewr_service_uses_injected_repository_provider():
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    employee_repo = MagicMock()
    employee = MagicMock(user_id=7)
    employee_repo.get_by_id.return_value = employee
    provider = MagicMock()
    provider.employees.return_value = employee_repo

    service = EmployeeWorkRegistrationService(session_factory, repository_provider=provider)
    user = type("User", (), {"id": 7})()
    service._scope(123, user)

    provider.employees.assert_called_once_with(session)
    employee_repo.get_by_id.assert_called_once_with(123)


def test_ewr_service_does_not_import_or_construct_concrete_repository():
    path = SERVICES_DIR / "employee_work_registration_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    concrete_imports = []
    concrete_constructors = []
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

    assert concrete_imports == []
    assert concrete_constructors == []
