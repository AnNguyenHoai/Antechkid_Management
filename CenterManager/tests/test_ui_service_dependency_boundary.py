"""Static UI -> Service architecture guard for EP-ARCH-03.22.

The UI layer may depend on application services, but must not bypass the
service boundary by importing repositories or SQLAlchemy, constructing
repositories/sessions, or issuing ORM/query operations directly.

Composition/bootstrap code is intentionally outside this guard: only modules
under ``centermanager.ui`` are audited.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = PROJECT_ROOT / "src" / "centermanager" / "ui"

ALLOWED_SERVICE_PREFIXES = (
    "centermanager.services",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "centermanager.repositories",
    "sqlalchemy",
)
FORBIDDEN_SESSION_NAMES = {
    "Session",
    "sessionmaker",
    "scoped_session",
}
FORBIDDEN_QUERY_METHODS = {
    "query",
    "execute",
    "commit",
    "flush",
    "refresh",
    "delete",
    "add",
    "add_all",
}


class _UIDependencyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.forbidden_imports: list[str] = []
        self.service_imports: list[str] = []
        self.session_constructors: list[str] = []
        self.query_operations: list[str] = []
        self.repository_names: list[str] = []

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
        if module in ALLOWED_SERVICE_PREFIXES or any(
            module.startswith(prefix + ".") for prefix in ALLOWED_SERVICE_PREFIXES
        ):
            self.service_imports.append(module)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_SESSION_NAMES:
                self.session_constructors.append(node.func.id)
            if node.func.id in FORBIDDEN_QUERY_METHODS:
                self.query_operations.append(node.func.id)
            if node.func.id.endswith("Repository"):
                self.repository_names.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in FORBIDDEN_SESSION_NAMES:
                self.session_constructors.append(attr)
            if attr in FORBIDDEN_QUERY_METHODS:
                self.query_operations.append(attr)
            if attr.endswith("Repository"):
                self.repository_names.append(attr)
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

    assert not visitor.forbidden_imports, (
        f"UI module {relative} bypasses Service boundary with forbidden imports: "
        f"{visitor.forbidden_imports}"
    )
    assert not visitor.repository_names, (
        f"UI module {relative} references/constructs concrete repositories: "
        f"{visitor.repository_names}"
    )
    assert not visitor.session_constructors, (
        f"UI module {relative} constructs database sessions directly: "
        f"{visitor.session_constructors}"
    )
    assert not visitor.query_operations, (
        f"UI module {relative} performs direct persistence operations: "
        f"{visitor.query_operations}"
    )


def test_ui_service_dependencies_are_explicit_application_dependencies() -> None:
    modules_with_services = 0
    for source_path in _ui_python_files():
        visitor = _inspect(source_path)
        if visitor.service_imports:
            modules_with_services += 1

    # The UI package currently contains service-driven application shells/pages.
    # Keep this assertion intentionally broad: it verifies the contract is
    # exercised without hard-coding a fragile list of individual widgets.
    assert modules_with_services > 0


def test_ui_dependency_guard_is_recursive_and_excludes_only_package_initializers() -> None:
    paths = _ui_python_files()
    assert paths
    assert all(path.parent == UI_DIR or path.parent.is_relative_to(UI_DIR) for path in paths)
    assert not any(path.name == "__init__.py" for path in paths)
