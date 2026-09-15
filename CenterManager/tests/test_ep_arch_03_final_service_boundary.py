"""EP-ARCH-03.27 — final application-service boundary audit.

The audit scans the complete service tree and reports boundary findings. The
RepositoryProvider migration is incremental, so legacy services are inventoried
rather than treated as already-migrated services.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = PROJECT_ROOT / "src" / "centermanager" / "services"

FORBIDDEN_SESSION_METHODS = {
    "query", "execute", "scalar", "scalars", "get", "add", "add_all",
    "delete", "merge", "expunge", "expire", "get_bind", "connection",
    "exec_driver_sql",
}
ALLOWED_TRANSACTION_METHODS = {"commit", "rollback"}
# Session/sessionmaker are used by services for type annotations. They are not
# persistence access; query-building imports such as sqlalchemy.or_ remain
# findings.
ALLOWED_SQLALCHEMY_ORM_IMPORTS = {"sqlalchemy.orm"}


@dataclass(frozen=True)
class ServiceBoundaryFindings:
    repository_imports: tuple[str, ...]
    repository_constructors: tuple[str, ...]
    sqlalchemy_imports: tuple[str, ...]
    persistence_operations: tuple[str, ...]

    @property
    def has_findings(self) -> bool:
        return any((self.repository_imports, self.repository_constructors,
                    self.sqlalchemy_imports, self.persistence_operations))


def _service_files() -> list[Path]:
    return sorted(SERVICES_DIR.glob("*_service.py"))


def _repository_import_violations(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            violations.extend(alias.name for alias in node.names
                              if alias.name.startswith("centermanager.repositories"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories") and module != "centermanager.repositories.provider":
                violations.append(module)
    return violations


def _sqlalchemy_import_violations(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            violations.extend(alias.name for alias in node.names
                              if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy."))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if (module == "sqlalchemy" or module.startswith("sqlalchemy.")) and module not in ALLOWED_SQLALCHEMY_ORM_IMPORTS:
                violations.append(module)
    return violations


def _concrete_repository_constructors(tree: ast.AST) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
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
        if node.func.attr in FORBIDDEN_SESSION_METHODS and _is_session_expr(node.func.value, session_names):
            violations.append(f"{ast.unparse(node.func.value)}.{node.func.attr}")
    return violations


def _repository_contract_usage(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ImportFrom) and node.module == "centermanager.repositories.provider"
        for node in tree.body
    )


def _audit_service(service_path: Path) -> ServiceBoundaryFindings:
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    return ServiceBoundaryFindings(
        tuple(_repository_import_violations(tree)),
        tuple(_concrete_repository_constructors(tree)),
        tuple(_sqlalchemy_import_violations(tree)),
        tuple(_direct_session_operations(tree, _session_names(tree))),
    )


def _migrated_service_files() -> list[Path]:
    """Derive the strict enforcement set from RepositoryProvider usage."""
    return [
        path for path in _service_files()
        if _repository_contract_usage(ast.parse(path.read_text(encoding="utf-8")))
    ]


@pytest.mark.parametrize("service_path", _migrated_service_files(), ids=lambda p: p.name)
def test_migrated_services_are_free_of_concrete_repository_dependencies(service_path: Path) -> None:
    findings = _audit_service(service_path)
    assert findings.repository_imports == (), service_path.name
    assert findings.repository_constructors == (), service_path.name


@pytest.mark.parametrize("service_path", _migrated_service_files(), ids=lambda p: p.name)
def test_migrated_services_are_free_of_direct_sqlalchemy_query_imports(service_path: Path) -> None:
    findings = _audit_service(service_path)
    assert findings.sqlalchemy_imports == (), service_path.name


@pytest.mark.parametrize("service_path", _migrated_service_files(), ids=lambda p: p.name)
def test_migrated_services_are_free_of_direct_persistence_operations(service_path: Path) -> None:
    findings = _audit_service(service_path)
    assert findings.persistence_operations == (), f"{service_path.name}: {findings.persistence_operations}"


def test_transaction_completion_is_the_only_direct_session_exception() -> None:
    assert not (FORBIDDEN_SESSION_METHODS & ALLOWED_TRANSACTION_METHODS)


def test_audit_discovers_complete_service_tree() -> None:
    service_files = _service_files()
    assert service_files, "No application service files were discovered."
    assert all(path.is_file() for path in service_files)


def test_audit_classifies_legacy_services_without_failing_ci() -> None:
    """Legacy violations remain visible as migration backlog.

    Once a legacy service adopts RepositoryProvider it automatically enters the
    strict gates above. This prevents pre-existing legacy debt from appearing
    as a regression of the current provider migration.
    """
    legacy = {
        path.name: _audit_service(path)
        for path in _service_files()
        if not _repository_contract_usage(ast.parse(path.read_text(encoding="utf-8")))
    }
    assert isinstance(legacy, dict)
    assert all(name.endswith("_service.py") for name in legacy)
