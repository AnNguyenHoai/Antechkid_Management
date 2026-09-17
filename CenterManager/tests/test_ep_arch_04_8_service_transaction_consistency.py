"""EP-ARCH-04.8 — application-service transaction consistency gate.

Contract:
- application services may own transaction boundaries;
- repository modules own no commit/rollback lifecycle;
- every service commit must have an explicit rollback path in the same service method;
- services must not silently mix transaction-owned and non-owned session lifecycles;
- transaction ownership must remain visible in source and consistent across mutating methods.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _service_files() -> list[Path]:
    return sorted(SERVICES.glob("*_service.py"))


def _repository_files() -> list[Path]:
    return sorted(REPOSITORIES.glob("*.py"))


def _transaction_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"commit", "rollback"}:
            calls.append(node)
    return calls


def _method_defs(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(node)
    return methods


def _contains_transaction_call(node: ast.AST, method_name: str) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Attribute) and child.func.attr == method_name:
            return True
    return False


def _exception_handlers(node: ast.AST) -> list[ast.ExceptHandler]:
    return [child for child in ast.walk(node) if isinstance(child, ast.ExceptHandler)]


def _handler_contains(node: ast.ExceptHandler, method_name: str) -> bool:
    return _contains_transaction_call(node, method_name)


def test_ep_arch_04_8_repositories_do_not_control_transactions():
    violations: list[str] = []
    for path in _repository_files():
        if path.name == "__init__.py":
            continue
        tree = _parse(path)
        for call in _transaction_calls(tree):
            method = call.func.attr  # type: ignore[union-attr]
            violations.append(f"{path.name}:{call.lineno}: repository calls session.{method}()")
    assert not violations, "Repository transaction ownership drift detected:\n" + "\n".join(violations)


def test_ep_arch_04_8_service_commit_requires_same_method_rollback_path():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for method in _method_defs(tree):
            if not _contains_transaction_call(method, "commit"):
                continue
            if _contains_transaction_call(method, "rollback"):
                continue
            # A commit inside a method without rollback in that same method leaves
            # exception-driven transaction recovery implicit and inconsistent.
            violations.append(f"{path.name}:{method.lineno}: {method.name}() commits without rollback path")
    assert not violations, "Service transaction boundary must provide an explicit rollback path:\n" + "\n".join(violations)


def test_ep_arch_04_8_service_rollback_is_exception_guarded():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for method in _method_defs(tree):
            if not _contains_transaction_call(method, "rollback"):
                continue
            handlers = _exception_handlers(method)
            if not any(_handler_contains(handler, "rollback") for handler in handlers):
                violations.append(f"{path.name}:{method.lineno}: {method.name}() rollback must be inside an exception handler")
    assert not violations, "Service rollback must be explicitly tied to exception handling:\n" + "\n".join(violations)
