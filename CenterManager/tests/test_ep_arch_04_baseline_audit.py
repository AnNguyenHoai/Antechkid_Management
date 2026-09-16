"""EP-ARCH-04.1 — global AST service-boundary regression gate."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
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

ALLOWED_SQLALCHEMY_IMPORTS = {
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


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _service_names() -> set[str]:
    return {path.name for path in _service_files()}


def _inventory_row(source: str, service_name: str) -> str:
    start = source.index(f"`{service_name}`")
    return source[start : source.index("\n", start)]


def test_ep_arch_04_1_discovers_complete_service_tree():
    service_files = _service_files()
    assert service_files, "service tree is empty"
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in sorted(_service_names()):
        assert f"`{service_name}`" in source, service_name


def test_ep_arch_04_1_global_service_boundary_blocks_concrete_repository_imports():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("centermanager.repositories.") and module != "centermanager.repositories.provider":
                    violations.append(f"{path.name}: concrete repository import {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("centermanager.repositories.") and alias.name != "centermanager.repositories.provider":
                        violations.append(f"{path.name}: concrete repository import {alias.name}")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_1_global_service_boundary_blocks_concrete_repository_construction():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
                violations.append(f"{path.name}:{node.lineno}: constructs {node.func.id}()")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_1_global_service_boundary_blocks_disallowed_sqlalchemy_imports():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("sqlalchemy") and module not in ALLOWED_SQLALCHEMY_IMPORTS:
                    violations.append(f"{path.name}:{node.lineno}: imports {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("sqlalchemy"):
                        violations.append(f"{path.name}:{node.lineno}: imports {alias.name}")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_1_global_service_boundary_blocks_direct_session_operations():
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
                violations.append(f"{path.name}:{node.lineno}: session.{node.func.attr}()")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_1_non_repository_classification_is_explicit():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in sorted(NON_REPOSITORY_SERVICES):
        row = _inventory_row(source, service_name)
        assert "| NON_REPOSITORY |" in row, row


def test_ep_arch_04_1_provider_import_is_the_only_repository_boundary_import():
    for path in _service_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "centermanager.repositories.provider":
                imported = {alias.name for alias in node.names}
                assert "RepositoryProvider" in imported or "create_default_repository_provider" in imported, (
                    f"{path.name}: provider import must expose RepositoryProvider or its default factory"
                )
