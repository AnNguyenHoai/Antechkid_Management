"""EP-ARCH-04 — baseline contracts for service/repository architecture.

These tests intentionally avoid modifying production behavior. They establish
source-derived contracts that the current architecture baseline must satisfy.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"
PROVIDER = REPOSITORIES / "provider.py"
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"

FORBIDDEN_SESSION_OPERATIONS = {
    "query",
    "execute",
    "scalar",
    "scalars",
    "get",
    "add",
    "add_all",
    "delete",
    "merge",
    "expunge",
    "expire",
    "get_bind",
    "connection",
    "exec_driver_sql",
    "refresh",
    "flush",
}

ALLOWED_SQLALCHEMY_IMPORT_PREFIXES = {
    "sqlalchemy.orm",
}

NON_REPOSITORY_SERVICES = {
    "authorization_service.py",
    "auto_report_service.py",
    "backup_operations_service.py",
    "configuration_service.py",
    "finance_dashboard_service.py",
    "git_config_service.py",
    "system_operations_service.py",
}


def _service_files() -> list[Path]:
    return sorted(SERVICES.glob("*_service.py"))


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _dotted_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _is_repository_provider_import(node: ast.ImportFrom) -> bool:
    return node.module == "centermanager.repositories.provider" and any(
        alias.name == "RepositoryProvider" for alias in node.names
    )


def test_ep_arch_04_discovers_complete_service_tree():
    service_files = _service_files()
    assert service_files, "service tree is empty"
    source_names = {path.name for path in service_files}
    inventory = INVENTORY.read_text(encoding="utf-8")
    for service_name in sorted(source_names):
        assert f"`{service_name}`" in inventory, service_name


def test_ep_arch_04_repository_provider_has_no_missing_repository_module_files():
    tree = _parse(PROVIDER)
    provider_modules: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module and node.module.startswith("centermanager.repositories.") and node.module != "centermanager.repositories.provider":
            provider_modules.add(node.module.rsplit(".", 1)[-1] + ".py")

    repository_files = {path.name for path in REPOSITORIES.glob("*_repository.py")}
    missing = sorted(provider_modules - repository_files)
    assert not missing, f"RepositoryProvider imports missing repository modules: {missing}"


def test_ep_arch_04_provider_declares_production_factory_for_every_declared_repository():
    tree = _parse(PROVIDER)
    imports: dict[str, str] = {}
    protocol_methods: set[str] = set()
    concrete_methods: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("centermanager.repositories."):
            for alias in node.names:
                if alias.name.endswith("Repository"):
                    imports[alias.name] = alias.name
        if isinstance(node, ast.ClassDef) and node.name in {"RepositoryProvider", "SqlAlchemyRepositoryProvider"}:
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name != "__init__":
                    if node.name == "RepositoryProvider":
                        protocol_methods.add(method.name)
                    else:
                        concrete_methods.add(method.name)

    expected_repository_imports = {
        name for name in imports if name.endswith("Repository")
    }
    assert expected_repository_imports, "RepositoryProvider must expose concrete repository types"
    assert protocol_methods == concrete_methods, (
        "RepositoryProvider protocol and SqlAlchemyRepositoryProvider implementation must expose the same factory methods"
    )


def test_ep_arch_04_global_service_boundary_has_no_concrete_repository_imports_or_construction():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("centermanager.repositories."):
                if node.module != "centermanager.repositories.provider":
                    violations.append(f"{path.name}: concrete repository import {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("centermanager.repositories.") and alias.name != "centermanager.repositories.provider":
                        violations.append(f"{path.name}: concrete repository import {alias.name}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id.endswith("Repository"):
                    violations.append(f"{path.name}: concrete repository construction {node.func.id}()")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_global_service_boundary_restricts_sqlalchemy_imports():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("sqlalchemy"):
                if node.module not in ALLOWED_SQLALCHEMY_IMPORT_PREFIXES:
                    violations.append(f"{path.name}: disallowed SQLAlchemy import {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("sqlalchemy"):
                        violations.append(f"{path.name}: disallowed SQLAlchemy import {alias.name}")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_global_service_boundary_blocks_direct_session_persistence_operations():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in FORBIDDEN_SESSION_OPERATIONS:
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Name) and receiver.id == "session":
                violations.append(f"{path.name}: session.{node.func.attr}()")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_inventory_non_repository_classification_is_explicit():
    inventory = INVENTORY.read_text(encoding="utf-8")
    for service_name in sorted(NON_REPOSITORY_SERVICES):
        row_start = inventory.index(f"`{service_name}`")
        row = inventory[row_start : inventory.index("\n", row_start)]
        assert "| NON_REPOSITORY |" in row, row
