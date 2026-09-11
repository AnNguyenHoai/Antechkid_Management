"""Regression coverage for PermissionService repository dependency injection."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from centermanager.services.permission_service import PermissionService


SERVICE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "centermanager"
    / "services"
    / "permission_service.py"
)


def test_permission_service_uses_injected_repositories_for_account_reads():
    session = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session

    provider = MagicMock()
    users = MagicMock()
    roles = MagicMock()
    user = MagicMock()
    user.id = 42
    users.get_by_id_with_role.return_value = user
    provider.users.return_value = users
    provider.roles.return_value = roles

    service = PermissionService(factory, repository_provider=provider)

    assert service.get_user(42) is user
    provider.users.assert_called_once_with(session)
    users.get_by_id_with_role.assert_called_once_with(42)


def test_permission_service_has_no_concrete_repository_or_sqlalchemy_imports():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))

    forbidden_imports: list[str] = []
    concrete_constructors: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy."):
                    forbidden_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "sqlalchemy" or module.startswith("sqlalchemy."):
                forbidden_imports.append(module)
            if module.startswith("centermanager.repositories") and module != "centermanager.repositories.provider":
                forbidden_imports.append(module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
                concrete_constructors.append(node.func.id)
            elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Repository"):
                concrete_constructors.append(node.func.attr)

    assert forbidden_imports == []
    assert concrete_constructors == []
