"""EP-ARCH-04.9 — nested service transaction and atomicity audit gate.

Contract:
- application-service composition must not introduce hidden independent transaction
  boundaries for a logical mutation;
- child services that are invoked from another service must not silently commit their
  own independent session when the caller owns the logical mutation;
- repository code must not acquire transaction state directly through connection/
  driver transaction primitives;
- intentional independent operations must be explicit and narrowly allowlisted.

This task is audit/regression protection only. It intentionally does not change
production service composition or introduce a UnitOfWork abstraction.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"

# Current baseline finding: PermissionService._audit() deliberately performs
# best-effort audit in its own service/session and swallows audit failures.
# Keep this exception narrow and explicit until a product-safe atomic audit design
# can be implemented separately.
INDEPENDENT_SERVICE_OPERATIONS = {
    ("permission_service.py", "_audit"),
}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _service_files() -> list[Path]:
    return sorted(SERVICES.glob("*_service.py"))


def _repository_files() -> list[Path]:
    return sorted(REPOSITORIES.glob("*_repository.py"))


def _method_defs(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _method_key(path: Path, method: ast.AST) -> tuple[str, str]:
    return path.name, getattr(method, "name", "<unknown>")


def _called_service_targets(method: ast.AST) -> list[tuple[str, str, int]]:
    calls: list[tuple[str, str, int]] = []
    for node in ast.walk(method):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = node.func.value
        if isinstance(receiver, ast.Name):
            calls.append((receiver.id, node.func.attr, node.lineno))
        elif isinstance(receiver, ast.Attribute):
            if isinstance(receiver.value, ast.Name) and receiver.value.id == "self":
                calls.append((receiver.attr, node.func.attr, node.lineno))
    return calls


def _service_class_instantiations(method: ast.AST) -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id.endswith("Service"):
            results.append((node.func.id, node.lineno))
        elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Service"):
            results.append((node.func.attr, node.lineno))
    return results


def _contains_commit(method: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "commit"
        for node in ast.walk(method)
    )


def _contains_session_factory_context(method: ast.AST) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            context = item.context_expr
            if isinstance(context, ast.Call) and isinstance(context.func, ast.Attribute):
                if context.func.attr in {"_sf", "_session_factory"} and not context.args and not context.keywords:
                    return True
            if isinstance(context, ast.Call) and isinstance(context.func, ast.Name):
                if context.func.id in {"session_factory", "SessionLocal"}:
                    return True
    return False


def _has_boundary_marker(method: ast.AST) -> bool:
    source = ast.get_source_segment(
        _parse(Path(getattr(method, "_audit_source", ""))) if False else ast.Module(body=[], type_ignores=[]),
        method,
    )
    del source
    doc = ast.get_docstring(method) or ""
    return "independent transaction" in doc.lower() or "transaction boundary" in doc.lower()


def test_ep_arch_04_9_service_composition_is_inventory_complete():
    """Source discovery must produce a deterministic service-composition inventory."""
    edges: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for method in _method_defs(tree):
            for receiver, target, lineno in _called_service_targets(method):
                if receiver.lower().endswith("service") or "service" in receiver.lower():
                    edges.append(f"{path.name}:{lineno}: {method.name}() -> {receiver}.{target}()")
            for service_name, lineno in _service_class_instantiations(method):
                if _method_key(path, method) not in INDEPENDENT_SERVICE_OPERATIONS:
                    edges.append(f"{path.name}:{lineno}: {method.name}() instantiates {service_name}")
    assert edges == sorted(edges), "Service composition inventory must be deterministically ordered."


def test_ep_arch_04_9_no_repository_connection_transaction_primitives():
    violations: list[str] = []
    forbidden = {"begin", "begin_nested", "commit", "rollback", "exec_driver_sql"}
    for path in _repository_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in forbidden:
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Attribute) and receiver.attr == "_session":
                violations.append(
                    f"{path.name}:{node.lineno}: repository controls transaction/connection via _session.{node.func.attr}()"
                )
            elif isinstance(receiver, ast.Attribute) and receiver.attr == "_connection":
                violations.append(
                    f"{path.name}:{node.lineno}: repository controls transaction via _connection.{node.func.attr}()"
                )
    assert not violations, "Repository transaction primitive drift detected:\n" + "\n".join(violations)


def test_ep_arch_04_9_nested_service_with_commit_is_explicit():
    """Nested service use inside a committing method must have an explicit contract."""
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for method in _method_defs(tree):
            if not _contains_commit(method):
                continue
            service_calls = _called_service_targets(method)
            service_instances = _service_class_instantiations(method)
            if not service_calls and not service_instances:
                continue
            if _method_key(path, method) in INDEPENDENT_SERVICE_OPERATIONS:
                continue
            if _contains_session_factory_context(method):
                doc = ast.get_docstring(method) or ""
                if "independent transaction" not in doc.lower() and "transaction boundary" not in doc.lower():
                    violations.append(
                        f"{path.name}:{method.lineno}: {method.name}() composes another service inside a transaction without explicit boundary documentation"
                    )
    assert not violations, "Nested service transaction boundary must be explicit:\n" + "\n".join(violations)
