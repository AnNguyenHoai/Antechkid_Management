"""Static UI -> Service architecture guard for EP-ARCH-03.22.

The UI layer may depend on application services, but must not bypass the
service boundary by importing repositories or SQLAlchemy, constructing
repositories/sessions, or issuing persistence operations directly.

The persistence-operation check is intentionally receiver-aware. Qt/PySide
widgets commonly expose methods such as ``refresh()``, ``add()`` and
``delete()``; treating every call with those method names as a database
operation creates false positives. We therefore only classify such calls as
persistence access when their receiver is explicitly session/repository-like.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = PROJECT_ROOT / "src" / "centermanager" / "ui"

FORBIDDEN_IMPORT_PREFIXES = ("centermanager.repositories", "sqlalchemy")
FORBIDDEN_SESSION_NAMES = {"Session", "sessionmaker", "scoped_session"}
FORBIDDEN_QUERY_METHODS = {
    "query", "execute", "commit", "flush", "refresh", "delete", "add", "add_all",
}
PERSISTENCE_RECEIVER_NAMES = {
    "session", "db_session", "database_session", "transaction", "repository",
    "repositories", "repo", "repos", "_session", "_db_session",
    "_database_session", "_transaction", "_repository", "_repositories",
    "_repo", "_repos",
}


def _attribute_parts(node: ast.AST) -> list[str]:
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return parts


class _UIDependencyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.forbidden_imports: list[str] = []
        self.service_imports: list[str] = []
        self.session_constructors: list[str] = []
        self.query_operations: list[str] = []
        self.repository_references: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name
            if name == "centermanager.services" or name.startswith("centermanager.services."):
                self.service_imports.append(name)
            if any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES):
                self.forbidden_imports.append(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES):
            self.forbidden_imports.append(module)
        if module == "centermanager.services" or module.startswith("centermanager.services."):
            self.service_imports.append(module)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in FORBIDDEN_SESSION_NAMES:
                self.session_constructors.append(name)
            if name.endswith("Repository"):
                self.repository_references.append(name)
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
            if name in FORBIDDEN_SESSION_NAMES:
                self.session_constructors.append(name)
            if name in FORBIDDEN_QUERY_METHODS and any(
                part in PERSISTENCE_RECEIVER_NAMES for part in _attribute_parts(node.func.value)
            ):
                self.query_operations.append(name)
            if name.endswith("Repository"):
                self.repository_references.append(name)
        self.generic_visit(node)


def _ui_python_files() -> list[Path]:
    return sorted(path for path in UI_DIR.rglob("*.py") if path.name != "__init__.py")


def _inspect(path: Path) -> _UIDependencyVisitor:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = _UIDependencyVisitor()
    visitor.visit(tree)
    return visitor


@pytest.mark.parametrize("source_path", _ui_python_files(), ids=lambda p: str(p.relative_to(UI_DIR)))
def test_ui_modules_do_not_bypass_service_boundary(source_path: Path) -> None:
    visitor = _inspect(source_path)
    relative = source_path.relative_to(UI_DIR)
    assert not visitor.forbidden_imports, f"UI module {relative} uses forbidden imports: {visitor.forbidden_imports}"
    assert not visitor.repository_references, f"UI module {relative} references repositories: {visitor.repository_references}"
    assert not visitor.session_constructors, f"UI module {relative} constructs DB sessions: {visitor.session_constructors}"
    assert not visitor.query_operations, f"UI module {relative} performs persistence operations: {visitor.query_operations}"


def test_ui_contains_service_driven_modules() -> None:
    assert any(_inspect(path).service_imports for path in _ui_python_files())


def test_ui_dependency_guard_covers_nested_packages() -> None:
    paths = _ui_python_files()
    assert paths
    assert any(path.parent != UI_DIR for path in paths)
