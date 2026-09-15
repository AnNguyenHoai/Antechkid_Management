"""Regression tests for the TeacherAssignmentService repository boundary."""
from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = PROJECT_ROOT / "src" / "centermanager" / "services" / "teacher_assignment_service.py"


def _tree() -> ast.AST:
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))


def test_teacher_assignment_service_imports_repository_provider_not_concrete_repositories() -> None:
    tree = _tree()
    concrete_imports: list[str] = []
    provider_imported = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "centermanager.repositories.provider":
                provider_imported = any(
                    alias.name == "RepositoryProvider" for alias in node.names
                )
            elif module.startswith("centermanager.repositories"):
                concrete_imports.append(module)
        elif isinstance(node, ast.Import):
            concrete_imports.extend(
                alias.name
                for alias in node.names
                if alias.name.startswith("centermanager.repositories")
            )

    assert provider_imported
    assert concrete_imports == []


def test_teacher_assignment_service_does_not_construct_concrete_repositories() -> None:
    tree = _tree()
    constructors: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
            constructors.append(node.func.id)
        elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Repository"):
            constructors.append(node.func.attr)

    assert constructors == []
