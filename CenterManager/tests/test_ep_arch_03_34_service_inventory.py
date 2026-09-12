"""EP-ARCH-03.34 — final service inventory and remaining boundary audit.

This test produces a deterministic, machine-readable inventory of every
application service and its current repository-boundary state. It does not
change production behavior and intentionally keeps legacy findings visible
for the next migration slices.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = PROJECT_ROOT / "src" / "centermanager" / "services"
INVENTORY_PATH = PROJECT_ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"
FORBIDDEN_SESSION_METHODS = {
    "query", "execute", "scalar", "scalars", "get", "add", "add_all",
    "delete", "merge", "expunge", "expire", "get_bind", "connection",
    "exec_driver_sql",
}
ALLOWED_SQLALCHEMY_ORM_IMPORTS = {"sqlalchemy.orm"}


@dataclass(frozen=True)
class Findings:
    repository_imports: tuple[str, ...]
    repository_constructors: tuple[str, ...]
    sqlalchemy_imports: tuple[str, ...]
    persistence_operations: tuple[str, ...]
    provider_usage: bool

    @property
    def strict_clean(self) -> bool:
        return not (
            self.repository_imports
            or self.repository_constructors
            or self.sqlalchemy_imports
            or self.persistence_operations
        )

    @property
    def status(self) -> str:
        if not self.provider_usage:
            return "LEGACY"
        return "PASS" if self.strict_clean else "VIOLATION"


def _service_files() -> list[Path]:
    return sorted(SERVICES_DIR.glob("*_service.py"))


def _repository_imports(tree: ast.Module) -> list[str]:
    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            found.extend(
                alias.name for alias in node.names
                if alias.name.startswith("centermanager.repositories")
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories") and module != "centermanager.repositories.provider":
                found.append(module)
    return found


def _sqlalchemy_imports(tree: ast.Module) -> list[str]:
    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            found.extend(
                alias.name for alias in node.names
                if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy.")
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if (module == "sqlalchemy" or module.startswith("sqlalchemy.")) and module not in ALLOWED_SQLALCHEMY_ORM_IMPORTS:
                found.append(module)
    return found


def _repository_constructors(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
            found.append(node.func.id)
        elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Repository"):
            found.append(node.func.attr)
    return found


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


def _direct_session_operations(tree: ast.AST, session_names: set[str]) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in FORBIDDEN_SESSION_METHODS:
            continue
        value = node.func.value
        is_session = isinstance(value, ast.Name) and value.id in session_names
        if is_session:
            found.append(f"{ast.unparse(value)}.{node.func.attr}")
    return found


def _provider_usage(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ImportFrom) and node.module == "centermanager.repositories.provider"
        for node in tree.body
    )


def _audit(path: Path) -> Findings:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return Findings(
        tuple(_repository_imports(tree)),
        tuple(_repository_constructors(tree)),
        tuple(_sqlalchemy_imports(tree)),
        tuple(_direct_session_operations(tree, _session_names(tree))),
        _provider_usage(tree),
    )


def _inventory_rows() -> list[tuple[str, Findings]]:
    return [(path.name, _audit(path)) for path in _service_files()]


def test_inventory_discovers_complete_service_tree() -> None:
    services = _service_files()
    assert services, "No application service files were discovered."
    assert all(path.is_file() for path in services)


def test_inventory_classifies_every_service() -> None:
    rows = _inventory_rows()
    assert rows
    assert len({name for name, _ in rows}) == len(rows)
    assert all(findings.status in {"LEGACY", "PASS", "VIOLATION"} for _, findings in rows)


def test_migrated_services_remain_strictly_clean() -> None:
    violations = [
        (name, findings)
        for name, findings in _inventory_rows()
        if findings.provider_usage and not findings.strict_clean
    ]
    assert not violations, [
        {
            "service": name,
            "repository_imports": findings.repository_imports,
            "repository_constructors": findings.repository_constructors,
            "sqlalchemy_imports": findings.sqlalchemy_imports,
            "persistence_operations": findings.persistence_operations,
        }
        for name, findings in violations
    ]


def test_inventory_is_committed_and_covers_current_service_tree() -> None:
    rows = dict(_inventory_rows())
    assert INVENTORY_PATH.is_file(), f"Missing inventory: {INVENTORY_PATH}"
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")
    assert "EP-ARCH-03 — Service Boundary Inventory" in inventory
    for service_name in rows:
        assert f"`{service_name}`" in inventory


def test_legacy_services_are_explicitly_marked_for_migration() -> None:
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")
    assert "LEGACY" in inventory
    assert "Next migration" in inventory


def test_inventory_contains_no_unknown_statuses() -> None:
    rows = _inventory_rows()
    assert all(findings.status in {"LEGACY", "PASS", "VIOLATION"} for _, findings in rows)
