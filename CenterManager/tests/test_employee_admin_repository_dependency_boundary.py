"""Regression coverage for the EmployeeAdminManagementService repository boundary."""
from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = PROJECT_ROOT / "src" / "centermanager" / "services" / "employee_admin_management_service.py"


def _tree() -> ast.AST:
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))


def test_employee_admin_service_uses_repository_provider_only() -> None:
    tree = _tree()
    repository_imports: list[str] = []
    provider_imports: list[str] = []
    concrete_constructors: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("centermanager.repositories"):
                    repository_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories"):
                if module == "centermanager.repositories.provider":
                    provider_imports.extend(alias.name for alias in node.names)
                else:
                    repository_imports.append(module)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name.endswith("Repository"):
                concrete_constructors.append(name)

    assert repository_imports == []
    assert "RepositoryProvider" in provider_imports
    assert concrete_constructors == []


def test_employee_admin_service_routes_all_persistence_access_through_provider() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "self._repository_provider.employee_work_registration_periods(session)" in source
    assert "self._repository_provider.employee_work_registrations(session)" in source
    assert "self._repository_provider.employees(session)" in source
    assert "session.query(" not in source
    assert "session.scalar(" not in source
