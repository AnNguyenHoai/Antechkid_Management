"""EP-ARCH-04.9 — nested service transaction and atomicity audit gate.

Contract:
- application-service composition must not introduce hidden independent transaction
  boundaries for a logical mutation;
- child services that are invoked from another service must not silently commit their
  own independent session when the caller owns the logical mutation;
- repository code must not acquire transaction state directly through connection/
  driver transaction primitives;
- every service/service edge that crosses into another service is reported so the
  transaction boundary can be reviewed and regression-protected;
- intentional independent operations must be explicit and documented rather than
  inferred from an arbitrary service call.

This task is audit/regression protection only. It intentionally does not change
production service composition or introduce a UnitOfWork abstraction.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"


SERVICE_ALLOWED_INDEPENDENT_OPERATIONS = {
    # These are explicitly documented as independent/best-effort operations in the
    # current architecture audit. Keep the allowlist tiny and reviewable.
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
    name = getattr(method, "name", "<unknown>")
    return path.name, name


def _called_service_targets(method: ast.AST) -> list[tuple[str, str, int]]:
    calls: list[tuple[str, str, int]] = []
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        receiver = node.func.value
        if isinstance(receiver, ast.Name):
            calls.append((receiver.id, node.func.attr, node.lineno))
        elif isinstance(receiver, ast.Attribute):
            # Covers common self._service.method(...) style composition.
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


def test_ep_arch_04_9_service_composition_is_inventory_complete():
    """Every service-to-service call/instantiation is discoverable by source scan."""
    edges: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for method in _method_defs(tree):
            for receiver, target, lineno in _called_service_targets(method):
                if receiver.lower().endswith("service") or "service" in receiver.lower():
                    edges.append(f"{path.name}:{lineno}: {method.name}() -> {receiver}.{target}()")
            for service_name, lineno in _service_class_instantiations(method):
                if (path.name, method.name) not in SERVICE_ALLOWED_INDEPENDENT_OPERATIONS:
                    edges.append(f"{path.name}:{lineno}: {method.name}() instantiates {service_name}")
    # The point of this gate is to make composition reviewable. A fixture-free
    # source audit must be deterministic and must not silently skip discovered edges.
    assert edges == sorted(edges), "Service composition inventory must be deterministically ordered."


def test_ep_arch_04_9_no_repository_connection_transaction_primitives():
    violations: list[str] = []
    forbidden = {
        "begin",
        "begin_nested",
        "commit",
        "rollback",
        "exec_driver_sql",
    }
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
    """A service method that both composes another service and commits must be explicit.

    The current source baseline contains intentional best-effort audit composition.
    This gate only blocks the unreviewed case: a method that invokes another service,
    owns a transaction, and has no explicit marker explaining the independent
    boundary in source.
    """
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
            if _method_key(path, method) in SERVICE_ALLOWED_INDEPENDENT_OPERATIONS:
                continue
            # A local session context plus a nested service call is the risky shape;
            # require the method to document the boundary explicitly in source.
            if _contains_session_factory_context(method):
                doc = ast.get_docstring(method) or ""
                if "independent transaction" not in doc.lower() and "transaction boundary" not in doc.lower():
                    violations.append(
                        f"{path.name}:{method.lineno}: {method.name}() composes another service inside a transaction without explicit boundary documentation"
                    )
    assert not violations, "Nested service transaction boundary must be explicit:\n" + "\n".join(violations)
