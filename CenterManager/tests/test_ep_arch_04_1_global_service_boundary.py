"""EP-ARCH-04.1 — dedicated global AST regression gate.

This gate dynamically discovers every application service and enforces the
repository boundary without maintaining a service allowlist.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"

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

ALLOWED_SQLALCHEMY_IMPORTS = {"sqlalchemy.orm"}


def _service_files() -> list[Path]:
    return sorted(SERVICES.glob("*_service.py"))


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_ep_arch_04_1_global_service_tree_is_non_empty():
    assert _service_files(), "No application service files were discovered"


def test_ep_arch_04_1_no_service_imports_concrete_repositories():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("centermanager.repositories.") and module != "centermanager.repositories.provider":
                    violations.append(f"{path.name}:{node.lineno}: import {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("centermanager.repositories.") and alias.name != "centermanager.repositories.provider":
                        violations.append(f"{path.name}:{node.lineno}: import {alias.name}")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_1_no_service_constructs_concrete_repositories():
    violations: list[str] = []
    for path in _service_files():
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id.endswith("Repository"):
                    violations.append(f"{path.name}:{node.lineno}: {node.func.id}()")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_1_no_service_imports_disallowed_sqlalchemy_modules():
    violations: list[str] = []
    for path in _service_files():
        for node in _parse(path).body:
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("sqlalchemy") and module not in ALLOWED_SQLALCHEMY_IMPORTS:
                    violations.append(f"{path.name}:{node.lineno}: from {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("sqlalchemy"):
                        violations.append(f"{path.name}:{node.lineno}: import {alias.name}")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_1_no_service_calls_forbidden_session_operations():
    violations: list[str] = []
    for path in _service_files():
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in FORBIDDEN_SESSION_OPERATIONS:
                continue
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "session":
                violations.append(f"{path.name}:{node.lineno}: session.{node.func.attr}()")
    assert not violations, "\n".join(violations)
