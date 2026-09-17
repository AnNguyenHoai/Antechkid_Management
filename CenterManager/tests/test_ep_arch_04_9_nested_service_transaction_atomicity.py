"""EP-ARCH-04.9 — nested service transaction and atomicity audit gate."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"

# Existing, deliberate best-effort audit boundary. AuditService.record() owns
# its own session by design and is not treated as business-transaction nesting.
INDEPENDENT_SERVICE_CLASSES = {"AuditService"}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _service_files() -> list[Path]:
    return sorted(SERVICES.glob("*_service.py"))


def _repository_files() -> list[Path]:
    return sorted(REPOSITORIES.glob("*_repository.py"))


def _method_defs(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _contains_commit(method: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "commit"
        for n in ast.walk(method)
    )


def _commit_lines(method: ast.AST) -> list[int]:
    return sorted(
        n.lineno
        for n in ast.walk(method)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "commit"
        and hasattr(n, "lineno")
    )


def _contains_session_factory_context(method: ast.AST) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            context = item.context_expr
            if (
                isinstance(context, ast.Call)
                and isinstance(context.func, ast.Attribute)
                and context.func.attr in {"_sf", "_session_factory"}
                and not context.args
                and not context.keywords
            ):
                return True
            if (
                isinstance(context, ast.Call)
                and isinstance(context.func, ast.Name)
                and context.func.id in {"session_factory", "SessionLocal"}
            ):
                return True
    return False


def _service_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        class_name = (
            func.id
            if isinstance(func, ast.Name) and func.id.endswith("Service")
            else func.attr
            if isinstance(func, ast.Attribute) and func.attr.endswith("Service")
            else None
        )
        if not class_name:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            aliases[target.id] = class_name
        elif (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        ):
            aliases[target.attr] = class_name
    return aliases


def _service_edges(path: Path, tree: ast.Module) -> list[str]:
    aliases = _service_aliases(tree)
    edges: list[str] = []
    for method in _method_defs(tree):
        for node in ast.walk(method):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            receiver = node.func.value
            receiver_name = (
                receiver.id
                if isinstance(receiver, ast.Name)
                else receiver.attr
                if isinstance(receiver, ast.Attribute)
                and isinstance(receiver.value, ast.Name)
                and receiver.value.id == "self"
                else None
            )
            if receiver_name in aliases:
                edges.append(
                    f"{path.name}:{node.lineno}: {method.name}() -> "
                    f"{aliases[receiver_name]}.{node.func.attr}()"
                )
    return sorted(edges)


def _transaction_methods_by_service() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in _service_files():
        tree = _parse(path)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith("Service"):
                methods = {
                    m.name
                    for m in node.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and _contains_commit(m)
                }
                if methods:
                    result[node.name] = methods
    return result


def _nested_transaction_calls(path: Path, tree: ast.Module) -> list[str]:
    aliases = _service_aliases(tree)
    transaction_methods = _transaction_methods_by_service()
    violations: list[str] = []
    for method in _method_defs(tree):
        if not _contains_commit(method) or not _contains_session_factory_context(method):
            continue

        # A child service that owns a commit boundary is only a hidden nested
        # transaction when it is invoked before the caller's transaction is
        # committed. Calls after the caller commit are sequential follow-up
        # operations, not nested transactions, and therefore do not violate
        # atomicity of the caller's transaction.
        commit_lines = _commit_lines(method)
        first_commit_line = commit_lines[0] if commit_lines else None
        if first_commit_line is None:
            continue

        for node in ast.walk(method):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if getattr(node, "lineno", first_commit_line) >= first_commit_line:
                continue

            receiver = node.func.value
            receiver_name = (
                receiver.id
                if isinstance(receiver, ast.Name)
                else receiver.attr
                if isinstance(receiver, ast.Attribute)
                and isinstance(receiver.value, ast.Name)
                and receiver.value.id == "self"
                else None
            )
            service_class = aliases.get(receiver_name)
            if not service_class or service_class in INDEPENDENT_SERVICE_CLASSES:
                continue
            if node.func.attr in transaction_methods.get(service_class, set()):
                violations.append(
                    f"{path.name}:{node.lineno}: {method.name}() invokes transaction-owning "
                    f"{service_class}.{node.func.attr}() before caller commit"
                )
    return violations


def test_ep_arch_04_9_service_composition_inventory_is_deterministic():
    edges: list[str] = []
    for path in _service_files():
        edges.extend(_service_edges(path, _parse(path)))
    assert edges == sorted(edges), "Service composition inventory must be deterministically ordered."


def test_ep_arch_04_9_no_repository_connection_transaction_primitives():
    violations: list[str] = []
    forbidden = {"begin", "begin_nested", "commit", "rollback", "exec_driver_sql"}
    for path in _repository_files():
        for node in ast.walk(_parse(path)):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Attribute)
                or node.func.attr not in forbidden
            ):
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Attribute) and receiver.attr in {"_session", "_connection"}:
                violations.append(
                    f"{path.name}:{node.lineno}: repository controls transaction via "
                    f"{receiver.attr}.{node.func.attr}()"
                )
    assert not violations, "Repository transaction primitive drift detected:\n" + "\n".join(violations)


def test_ep_arch_04_9_no_hidden_nested_transaction_boundary():
    violations: list[str] = []
    for path in _service_files():
        violations.extend(_nested_transaction_calls(path, _parse(path)))
    assert not violations, "Hidden nested service transaction boundary detected:\n" + "\n".join(violations)
