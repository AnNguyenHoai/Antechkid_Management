"""EP-ARCH-04.8 — application-service transaction consistency gate.

Contract:
- application services may own transaction boundaries;
- repository modules own no commit/rollback lifecycle;
- every service commit must have an exception-safe rollback path;
- rollback may be explicit in the same method or provided by an application-owned
  session context manager enclosing the commit;
- services must not silently mix transaction-owned and non-owned session lifecycles.
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
    return [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _contains_transaction_call(node: ast.AST, method_name: str) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == method_name
        for child in ast.walk(node)
    )


def _exception_handlers(node: ast.AST) -> list[ast.ExceptHandler]:
    return [child for child in ast.walk(node) if isinstance(child, ast.ExceptHandler)]


def _handler_contains(node: ast.ExceptHandler, method_name: str) -> bool:
    return _contains_transaction_call(node, method_name)


def _is_session_factory_context(node: ast.With) -> bool:
    for item in node.items:
        context = item.context_expr
        if isinstance(context, ast.Call) and isinstance(context.func, ast.Attribute):
            if context.func.attr in {"_sf", "_session_factory"} and not context.args and not context.keywords:
                return True
        if isinstance(context, ast.Call) and isinstance(context.func, ast.Name):
            if context.func.id in {"session_factory", "SessionLocal"}:
                return True
    return False


def _node_contains(root: ast.AST, target: ast.AST) -> bool:
    return any(child is target for child in ast.walk(root))


def _commit_has_context_manager_rollback_boundary(method: ast.AST) -> bool:
    """Verify every commit is enclosed by an application-owned session context."""
    commits = [
        child for child in ast.walk(method)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "commit"
    ]
    if not commits:
        return False

    session_contexts = [
        child for child in ast.walk(method)
        if isinstance(child, ast.With) and _is_session_factory_context(child)
    ]
    return all(
        any(_node_contains(context, commit) for context in session_contexts)
        for commit in commits
    )


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
            if _commit_has_context_manager_rollback_boundary(method):
                continue
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
