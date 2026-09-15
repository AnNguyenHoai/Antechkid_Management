"""EP-ARCH-03.28 — ExpenseService repository boundary regression tests."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "expense_service.py"


def test_expense_service_uses_repository_provider_not_concrete_repository():
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    imports = []
    constructors = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories.") and module != "centermanager.repositories.provider":
                imports.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("centermanager.repositories.") and alias.name != "centermanager.repositories.provider":
                    imports.append(alias.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
                constructors.append(node.func.id)
            elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Repository"):
                constructors.append(node.func.attr)

    assert imports == []
    assert constructors == []


def test_expense_service_has_injected_provider_with_legacy_constructor_compatibility():
    source = SERVICE.read_text(encoding="utf-8")
    assert "repository_provider: Optional[RepositoryProvider] = None" in source
    assert "self._repository_provider = repository_provider or create_default_repository_provider()" in source
    assert "self._repository_provider.expenses(session)" in source


def test_expense_service_keeps_transaction_completion_at_service_boundary():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session.commit()" in source
    assert "repo.refresh(expense)" in source
    assert "session.refresh(expense)" not in source
