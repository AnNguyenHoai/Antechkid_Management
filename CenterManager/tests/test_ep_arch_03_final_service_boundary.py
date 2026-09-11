"""Global architecture guard for application-service persistence boundaries.

The gate is intentionally strict about concrete repository dependencies, but
allows SQLAlchemy ORM type-only imports. Runtime persistence/query operations
remain forbidden in application services unless they are explicit transaction
orchestration (commit/rollback).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"

_ALLOWED_TRANSACTION_METHODS = {"commit", "rollback"}
_FORBIDDEN_SESSION_METHODS = {
    "query", "execute", "scalar", "scalars", "get", "add", "add_all",
    "delete", "flush", "refresh", "merge", "bulk_save_objects", "connection",
    "get_bind", "begin", "begin_nested", "close", "expunge", "expunge_all",
}


def _service_paths():
    return sorted(SERVICES_DIR.glob("*_service.py"))


def _repository_import_violations(tree: ast.AST):
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories") and module != "centermanager.repositories.provider":
                violations.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("centermanager.repositories") and alias.name != "centermanager.repositories.provider":
                    violations.append(alias.name)
    return sorted(violations)


def _sqlalchemy_import_violations(tree: ast.AST):
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "sqlalchemy" or module.startswith("sqlalchemy."):
                # ORM imports used solely for annotations/types do not cross the
                # persistence boundary. Query/engine/session APIs are checked
                # separately by the operation visitor.
                for alias in node.names:
                    if alias.name not in {"Session", "Mapped", "DeclarativeBase", "relationship"}:
                        violations.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("sqlalchemy"):
                    violations.append(alias.name)
    return sorted(set(violations))


def _persistence_operations(tree: ast.AST):
    operations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _FORBIDDEN_SESSION_METHODS:
                operations.append(f"{node.func.value.id if isinstance(node.func.value, ast.Name) else '<expr>'}.{node.func.attr}")
    return operations


@pytest.mark.parametrize("service_path", _service_paths(), ids=lambda p: p.name)
def test_every_application_service_is_free_of_concrete_repository_dependencies(service_path):
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    assert _repository_import_violations(tree) == [], service_path.name


@pytest.mark.parametrize("service_path", _service_paths(), ids=lambda p: p.name)
def test_every_application_service_is_free_of_direct_sqlalchemy_imports(service_path):
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    assert _sqlalchemy_import_violations(tree) == [], service_path.name


@pytest.mark.parametrize("service_path", _service_paths(), ids=lambda p: p.name)
def test_every_application_service_is_free_of_direct_persistence_operations(service_path):
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    operations = _persistence_operations(tree)
    assert operations == [], f"{service_path.name}: {operations}"


def test_transaction_orchestration_allowlist_is_explicit():
    assert _ALLOWED_TRANSACTION_METHODS == {"commit", "rollback"}


def test_service_tree_is_not_empty():
    assert _service_paths(), "Expected at least one application service to be audited"
