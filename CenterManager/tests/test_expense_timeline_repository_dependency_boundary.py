"""Regression tests for the EP-ARCH-03 expense timeline boundary."""
from __future__ import annotations

import ast
from pathlib import Path

from centermanager.repositories.provider import SqlAlchemyRepositoryProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = PROJECT_ROOT / "src" / "centermanager" / "services" / "expense_timeline_service.py"


def _parse_service() -> ast.Module:
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))


def test_expense_timeline_service_uses_repository_provider_only() -> None:
    tree = _parse_service()
    repository_imports: list[str] = []
    concrete_constructors: list[str] = []
    provider_imported = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("centermanager.repositories"):
            if node.module == "centermanager.repositories.provider":
                provider_imported = any(alias.name == "RepositoryProvider" for alias in node.names)
            else:
                repository_imports.append(node.module or "")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
                concrete_constructors.append(node.func.id)
            elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Repository"):
                concrete_constructors.append(node.func.attr)

    assert provider_imported
    assert repository_imports == []
    assert concrete_constructors == []


def test_expense_timeline_service_accepts_injected_provider() -> None:
    from centermanager.services.expense_timeline_service import ExpenseTimelineService

    provider = object()
    service = ExpenseTimelineService(lambda: None, repository_provider=provider)  # type: ignore[arg-type]

    assert service._repository_provider is provider


def test_sqlalchemy_provider_exposes_expense_timeline_repository() -> None:
    provider = SqlAlchemyRepositoryProvider()
    assert callable(provider.expense_timeline)
