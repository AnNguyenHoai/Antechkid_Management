from __future__ import annotations

import ast
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"

# These are persistence/session operations that application services must not
# invoke directly. Persistence belongs behind RepositoryProvider/repositories.
FORBIDDEN_SESSION_METHODS = {
    "query",
    "execute",
    "scalar",
    "scalars",
    "get",
    "add",
    "add_all",
    "delete",
    "flush",
    "refresh",
    "commit",
    "rollback",
    "merge",
}


def _service_files() -> list[Path]:
    return sorted(SERVICES_DIR.glob("*_service.py"))


def _is_session_name(name: str) -> bool:
    normalized = name.lower()
    return normalized in {"session", "db_session", "session_obj"} or normalized.endswith("_session")


def _is_repository_provider_migrated(tree: ast.Module) -> bool:
    """Return whether the service explicitly participates in the repository boundary.

    EP-ARCH-03 is being migrated incrementally. Legacy services that still own
    their persistence implementation are intentionally outside this gate until
    their migration task is completed. A service becomes covered when its
    constructor accepts a ``repository_provider`` dependency.
    """
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) or child.name != "__init__":
                continue
            arguments = child.args.posonlyargs + child.args.args + child.args.kwonlyargs
            if any(argument.arg == "repository_provider" for argument in arguments):
                return True
    return False


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


def _migrated_service_files() -> list[Path]:
    result: list[Path] = []
    for path in _service_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _is_repository_provider_migrated(tree):
            result.append(path)
    return result


def test_migrated_application_services_do_not_import_sqlalchemy_directly() -> None:
    violations: list[str] = []
    for path in _migrated_service_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _find_sqlalchemy_imports(tree)
        if imports:
            violations.append(f"{path.name}: {imports}")

    assert violations == [], (
        "RepositoryProvider-migrated services must not import SQLAlchemy directly; "
        f"use RepositoryProvider instead: {violations}"
    )


def test_migrated_application_services_do_not_execute_direct_session_operations() -> None:
    violations: list[str] = []
    for path in _migrated_service_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        operations = _find_direct_session_operations(tree)
        if operations:
            violations.append(f"{path.name}: {operations}")

    assert violations == [], (
        "RepositoryProvider-migrated services must not call persistence/session operations directly: "
        f"{violations}"
    )
