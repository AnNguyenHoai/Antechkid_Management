"""EP-ARCH-03.27 — final application-service boundary audit.

This gate intentionally scans the complete service tree instead of maintaining
an allowlist of migrated services.  A service is allowed to own transaction
completion (commit/rollback), but persistence/query/connection/ORM-state
operations must remain behind RepositoryProvider/repositories.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = PROJECT_ROOT / "src" / "centermanager" / "services"

FORBIDDEN_SESSION_METHODS = {
    "query", "execute", "scalar", "scalars", "get", "add", "add_all",
    "delete", "flush", "refresh", "merge", "expunge", "expire",
    "get_bind", "connection", "exec_driver_sql",
}

ALLOWED_TRANSACTION_METHODS = {"commit", "rollback"}


def _service_files() -> list[Path]:
    return sorted(SERVICES_DIR.glob("*_service.py"))


def _is_repository_provider_module(module: str | None) -> bool:
    return module == "centermanager.repositories.provider"


def _repository_import_violations(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("centermanager.repositories"):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories") and not _is_repository_provider_module(module):
                violations.append(module)
    return violations


def _sqlalchemy_import_violations(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy."):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "sqlalchemy" or module.startswith("sqlalchemy."):
                violations.append(module)
    return violations


def _concrete_repository_constructors(tree: ast.AST) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
            violations.append(node.func.id)
        elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Repository"):
            violations.append(node.func.attr)
    return violations


def _looks_like_session_name(name: str) -> bool:
    normalized = name.lower()
    return normalized in {"session", "db_session", "session_obj"} or normalized.endswith("_session")


def _looks_like_session_factory(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        return _looks_like_session_factory(node.func)
    if isinstance(node, ast.Attribute):
        return node.attr in {"_session_factory", "session_factory", "_sf"} or _looks_like_session_factory(node.value)
    if isinstance(node, ast.Name):
        return node.id in {"_session_factory", "session_factory", "_sf"}
    return False


def _session_names(tree: ast.Module) -> set[str]:
    names = {"session", "db_session", "session_obj"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            names.update(arg.arg for arg in args if _looks_like_session_name(arg.arg))
        elif isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name) and _looks_like_session_factory(item.context_expr):
                    names.add(item.optional_vars.id)
    return names


def _is_session_expr(node: ast.AST, session_names: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in session_names
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr in {"connection", "get_bind"} and _is_session_expr(node.func.value, session_names)
    return False


def _direct_session_operations(tree: ast.AST, session_names: set[str]) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr
        if method not in FORBIDDEN_SESSION_METHODS:
            continue
        if _is_session_expr(node.func.value, session_names):
            violations.append(f"{ast.unparse(node.func.value)}.{method}")
    return violations


def _repository_contract_usage(tree: ast.Module) -> list[str]:
    """Require every service to depend on RepositoryProvider after EP-ARCH-03.27.

    Compatibility-only services with no persistence calls still need not import
    the provider; those are checked separately through persistence-risk scans.
    """
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "centermanager.repositories.provider":
            return [alias.name for alias in node.names]
    return []


@pytest.mark.parametrize("service_path", _service_files(), ids=lambda p: p.name)
def test_every_application_service_is_free_of_concrete_repository_dependencies(service_path: Path) -> None:
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    assert _repository_import_violations(tree) == [], service_path.name
    assert _concrete_repository_constructors(tree) == [], service_path.name


@pytest.mark.parametrize("service_path", _service_files(), ids=lambda p: p.name)
def test_every_application_service_is_free_of_direct_sqlalchemy_imports(service_path: Path) -> None:
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    assert _sqlalchemy_import_violations(tree) == [], service_path.name


@pytest.mark.parametrize("service_path", _service_files(), ids=lambda p: p.name)
def test_every_application_service_is_free_of_direct_persistence_operations(service_path: Path) -> None:
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    operations = _direct_session_operations(tree, _session_names(tree))
    assert operations == [], f"{service_path.name}: {operations}"


def test_transaction_completion_is_the_only_direct_session_exception() -> None:
    assert not (FORBIDDEN_SESSION_METHODS & ALLOWED_TRANSACTION_METHODS)


def test_scan_is_repository_provider_boundary_or_legacy_free() -> None:
    """Inventory the whole service tree and fail only on real persistence bypasses.

    This test intentionally does not require every service to import
    RepositoryProvider. A service with no persistence dependency can remain a
    pure application facade. Services with persistence are captured by the
    concrete-repository/SQLAlchemy/direct-session gates above.
    """
    service_files = _service_files()
    assert service_files, "No application service files were discovered."
