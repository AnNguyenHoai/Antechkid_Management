from __future__ import annotations

import ast
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"

# EP-ARCH-03.20 is an incremental migration gate. Services are added here only
# after their production persistence access has been migrated behind the
# RepositoryProvider boundary.
MIGRATED_SERVICE_FILES = {
    "audit_service.py",
    "employee_schedule_service.py",
    "employee_work_registration_service.py",
}

FORBIDDEN_SESSION_METHODS = {
    "query", "execute", "scalar", "scalars", "get", "add", "add_all",
    "delete", "flush", "refresh", "commit", "rollback", "merge",
}


def _service_files() -> list[Path]:
    return sorted(path for path in SERVICES_DIR.glob("*_service.py") if path.name in MIGRATED_SERVICE_FILES)


def _is_session_name(name: str) -> bool:
    normalized = name.lower()
    return normalized in {"session", "db_session", "session_obj"} or normalized.endswith("_session")


def _find_direct_session_operations(tree: ast.AST) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in FORBIDDEN_SESSION_METHODS:
            continue
        owner = func.value
        if isinstance(owner, ast.Name) and _is_session_name(owner.id):
            violations.append(f"{owner.id}.{func.attr}")
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
        operations = _find_direct_session_operations(tree)
        if operations:
            violations.append(f"{path.name}: {operations}")
    assert violations == [], (
        "RepositoryProvider-migrated services must not call persistence/session operations directly: "
        f"{violations}"
    )
