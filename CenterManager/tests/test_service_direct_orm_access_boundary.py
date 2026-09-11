from __future__ import annotations

import ast
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"

MIGRATED_SERVICE_FILES = {
    "audit_service.py",
    "employee_schedule_service.py",
    "employee_work_registration_service.py",
}

# Commit/rollback are intentionally retained as transaction orchestration at
# the application boundary. Persistence, querying, connection access, and ORM
# state management belong below the service/repository boundary.
FORBIDDEN_SESSION_METHODS = {
    "query", "execute", "scalar", "scalars", "get", "add", "add_all",
    "delete", "flush", "refresh", "merge", "expunge", "expire",
    "get_bind", "connection", "exec_driver_sql",
}


def _service_files() -> list[Path]:
    return sorted(path for path in SERVICES_DIR.glob("*_service.py") if path.name in MIGRATED_SERVICE_FILES)


def _looks_like_session_name(name: str) -> bool:
    normalized = name.lower()
    return normalized in {"session", "db_session", "session_obj"} or normalized.endswith("_session")


def _looks_like_session_factory(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        return _looks_like_session_factory(node.func)
    if isinstance(node, ast.Attribute):
        return node.attr in {"_sf", "_session_factory", "session_factory"} or _looks_like_session_factory(node.value)
    if isinstance(node, ast.Name):
        return node.id in {"_sf", "_session_factory", "session_factory"}
    return False


def _session_names(tree: ast.Module) -> set[str]:
    """Discover variables that are session objects in service code."""
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


def _find_direct_session_operations(tree: ast.AST, session_names: set[str]) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in FORBIDDEN_SESSION_METHODS:
            continue
        if _is_session_expr(func.value, session_names):
            violations.append(f"{ast.unparse(func.value)}.{func.attr}")
    return violations


def _find_sqlalchemy_imports(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy."):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "sqlalchemy" or node.module.startswith("sqlalchemy.")):
                violations.append(node.module)
    return violations


def test_migrated_application_services_do_not_import_sqlalchemy_directly() -> None:
    violations: list[str] = []
    for path in _service_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _find_sqlalchemy_imports(tree)
        if imports:
            violations.append(f"{path.name}: {imports}")
    assert violations == [], (
        "RepositoryProvider-migrated services must not import SQLAlchemy directly: "
        f"{violations}"
    )


def test_migrated_application_services_do_not_execute_direct_session_operations() -> None:
    violations: list[str] = []
    for path in _service_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        operations = _find_direct_session_operations(tree, _session_names(tree))
        if operations:
            violations.append(f"{path.name}: {operations}")
    assert violations == [], (
        "RepositoryProvider-migrated services must not call persistence/session operations directly: "
        f"{violations}"
    )


def test_transaction_completion_remains_service_orchestration() -> None:
    assert "commit" not in FORBIDDEN_SESSION_METHODS
    assert "rollback" not in FORBIDDEN_SESSION_METHODS
