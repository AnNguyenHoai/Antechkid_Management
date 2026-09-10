# -*- coding: utf-8 -*-
"""EP-ARCH-03 regression tests for ClassService repository boundaries."""
from pathlib import Path
import ast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = PROJECT_ROOT / "src" / "centermanager" / "services" / "class_service.py"


def _tree() -> ast.AST:
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))


def test_class_service_imports_repository_provider_not_concrete_repositories():
    tree = _tree()
    provider_imported = False
    concrete_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "centermanager.repositories.provider":
                provider_imported = any(alias.name == "RepositoryProvider" for alias in node.names)
            elif module.startswith("centermanager.repositories."):
                concrete_imports.append(module)
        elif isinstance(node, ast.Import):
            concrete_imports.extend(
                alias.name for alias in node.names if alias.name.startswith("centermanager.repositories.")
            )

    assert provider_imported
    assert concrete_imports == []


def test_class_service_does_not_construct_concrete_repositories():
    tree = _tree()
    concrete = {
        "ClassRepository",
        "EnrollmentRepository",
        "SessionRepository",
        "TeacherAssignmentRepository",
        "TeacherRepository",
        "StudentRepository",
    }
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in concrete:
            violations.append(node.func.id)

    assert violations == []


def test_class_service_accepts_injected_repository_provider():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "repository_provider: Optional[RepositoryProvider] = None" in source
    assert "self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()" in source
    assert "self._repository_provider.classes(session)" in source
