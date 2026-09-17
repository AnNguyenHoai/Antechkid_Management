"""EP-ARCH-04.6 — repository API/lifecycle contract regression gate.

This gate is source-driven and verifies that concrete repositories expose a
stable application-facing contract without leaking ORM/session lifecycle
control through public APIs.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"
SERVICES = ROOT / "src" / "centermanager" / "services"

FORBIDDEN_REPOSITORY_PUBLIC_APIS = {"session", "commit", "rollback"}
FORBIDDEN_PUBLIC_SESSION_OPERATIONS = {
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
    "commit",
    "rollback",
}
REQUIRED_BASE_REPOSITORY_METHODS = {
    "add",
    "delete",
    "get_by_id",
    "list_all",
    "count",
    "flush",
    "refresh",
}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _repository_files() -> list[Path]:
    return sorted(REPOSITORIES.glob("*_repository.py"))


def _concrete_repository_files() -> list[Path]:
    return [p for p in _repository_files() if p.name not in {"base.py", "provider.py", "base_repository.py"}]


def _class_methods(path: Path, class_name: str | None = None) -> set[str]:
    tree = _parse(path)
    methods: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if class_name is not None and node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.add(item.name)
    return methods


def _repository_classes(path: Path) -> list[str]:
    tree = _parse(path)
    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name.endswith("Repository")
        and node.name != "BaseRepository"
    ]


def _direct_self_session_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = node.func.value
        if (
            isinstance(receiver, ast.Attribute)
            and isinstance(receiver.value, ast.Name)
            and receiver.value.id == "self"
            and receiver.attr == "session"
            and node.func.attr in FORBIDDEN_PUBLIC_SESSION_OPERATIONS
        ):
            calls.append(node)
    return calls


def test_ep_arch_04_6_base_repository_exposes_required_explicit_operations():
    base = REPOSITORIES / "base.py"
    assert base.exists(), "BaseRepository module is required."
    methods = _class_methods(base, "BaseRepository")
    missing = REQUIRED_BASE_REPOSITORY_METHODS - methods
    assert not missing, f"BaseRepository API is missing explicit operations: {sorted(missing)}"


def test_ep_arch_04_6_base_repository_has_no_public_session_or_transaction_escape_hatches():
    base = REPOSITORIES / "base.py"
    methods = _class_methods(base, "BaseRepository")
    leaked = methods & FORBIDDEN_REPOSITORY_PUBLIC_APIS
    assert not leaked, f"BaseRepository must not expose raw session/transaction APIs: {sorted(leaked)}"


def test_ep_arch_04_6_concrete_repository_files_define_one_repository_class():
    violations: list[str] = []
    for path in _concrete_repository_files():
        classes = _repository_classes(path)
        if len(classes) != 1:
            violations.append(f"{path.name}: expected exactly one concrete repository class, found {classes}")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_6_repositories_do_not_use_public_self_session_operations():
    violations: list[str] = []
    for path in _repository_files():
        for node in _direct_self_session_calls(_parse(path)):
            violations.append(f"{path.name}:{node.lineno}: self.session.{node.func.attr}()")
    assert not violations, (
        "Repositories must keep SQLAlchemy Session private behind _session and explicit repository methods:\n"
        + "\n".join(violations)
    )


def test_ep_arch_04_6_repository_public_methods_do_not_expose_session_or_transaction_control():
    violations: list[str] = []
    for path in _repository_files():
        for method in sorted(_class_methods(path)):
            if method in FORBIDDEN_REPOSITORY_PUBLIC_APIS:
                violations.append(f"{path.name}: public {method}()")
    assert not violations, "Repository public APIs must not expose raw session or transaction control:\n" + "\n".join(violations)


def test_ep_arch_04_6_application_services_only_reach_repositories_through_provider():
    violations: list[str] = []
    for path in sorted(SERVICES.glob("*_service.py")):
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or node.attr.startswith("_"):
                continue
            receiver = node.value
            if isinstance(receiver, ast.Name) and receiver.id in {"repo", "repository"} and node.attr in {
                "_session", "session", "commit", "rollback"
            }:
                violations.append(f"{path.name}:{node.lineno}: repository.{node.attr}")
            elif isinstance(receiver, ast.Attribute) and receiver.attr.endswith("repository") and node.attr in {
                "_session", "session", "commit", "rollback"
            }:
                violations.append(f"{path.name}:{node.lineno}: repository.{node.attr}")
    assert not violations, "Service consumers must use explicit repository APIs and provider-managed lifecycle:\n" + "\n".join(violations)


def test_ep_arch_04_6_repository_constructors_accept_a_session_dependency():
    violations: list[str] = []
    for path in _concrete_repository_files():
        tree = _parse(path)
        classes = [
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name.endswith("Repository")
        ]
        for cls in classes:
            init = next(
                (node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__"),
                None,
            )
            if init is None:
                violations.append(f"{path.name}:{cls.name}: missing __init__")
                continue
            parameters = init.args.args
            if not any(arg.arg == "session" for arg in parameters):
                violations.append(f"{path.name}:{cls.name}: __init__ must receive session explicitly")
    assert not violations, "Repository construction contract drift detected:\n" + "\n".join(violations)
