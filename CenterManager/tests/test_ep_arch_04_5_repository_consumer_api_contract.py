"""EP-ARCH-04.5 — Repository consumer/API contract regression gate."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"
PROVIDER = REPOSITORIES / "provider.py"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _service_files() -> list[Path]:
    return sorted(SERVICES.glob("*_service.py"))


def _repository_files() -> list[Path]:
    return sorted(REPOSITORIES.glob("*_repository.py"))


def _provider_factory_names() -> set[str]:
    tree = _parse(PROVIDER)
    protocol = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RepositoryProvider"
    )
    return {
        node.name
        for node in protocol.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _provider_usage(service_path: Path) -> set[str]:
    tree = _parse(service_path)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        receiver = func.value
        if (
            isinstance(receiver, ast.Attribute)
            and isinstance(receiver.value, ast.Name)
            and receiver.value.id == "self"
            and receiver.attr == "_repository_provider"
        ):
            names.add(func.attr)
    return names


def _repository_classes() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in _repository_files():
        if path.name in {"base.py", "provider.py"}:
            continue
        tree = _parse(path)
        classes = [
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name.endswith("Repository")
            and node.name != "BaseRepository"
        ]
        assert len(classes) == 1, (
            f"{path.name}: expected exactly one concrete repository class, found {classes}"
        )
        result[path.stem] = classes[0]
    return result


def _public_repository_methods() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in _repository_files():
        if path.name in {"base.py", "provider.py"}:
            continue
        tree = _parse(path)
        methods: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                methods.add(node.name)
        result[path.stem] = methods
    base = REPOSITORIES / "base.py"
    if base.exists():
        tree = _parse(base)
        base_methods = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        }
        result["base"] = base_methods
    return result


def test_ep_arch_04_5_all_provider_consumers_use_declared_factories():
    declared = _provider_factory_names()
    violations: list[str] = []
    for path in _service_files():
        for factory in sorted(_provider_usage(path)):
            if factory not in declared:
                violations.append(f"{path.name}: _repository_provider.{factory}() is not declared")
    assert not violations, "\n".join(violations)


def test_ep_arch_04_5_provider_consumer_surface_has_no_direct_repository_construction():
    violations: list[str] = []
    for path in _service_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id.endswith("Repository"):
                violations.append(f"{path.name}:{node.lineno}: constructs {func.id}()")
    assert not violations, "Application services must not construct concrete repositories:\n" + "\n".join(violations)


def test_ep_arch_04_5_repository_consumer_surface_has_no_raw_session_accessor():
    violations: list[str] = []
    session_attr_receivers = {"repo", "repository"}
    for path in _service_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or node.attr != "session":
                continue
            receiver = node.value
            if isinstance(receiver, ast.Name) and receiver.id in session_attr_receivers:
                violations.append(f"{path.name}:{node.lineno}: {receiver.id}.session")
            elif isinstance(receiver, ast.Attribute) and receiver.attr.endswith("repository"):
                violations.append(f"{path.name}:{node.lineno}: {receiver.attr}.session")
    assert not violations, "Repository consumers must not recover raw SQLAlchemy Session:\n" + "\n".join(violations)


def test_ep_arch_04_5_repository_public_api_uses_explicit_operations():
    """Guard against public session/transaction escape hatches on repositories."""
    forbidden = {"session", "commit", "rollback"}
    violations: list[str] = []
    for repo_path in _repository_files():
        tree = _parse(repo_path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in forbidden:
                violations.append(f"{repo_path.name}:{node.lineno}: public {node.name}() API")
    assert not violations, "Repository public APIs must not expose session or transaction control:\n" + "\n".join(violations)


def test_ep_arch_04_5_repository_consumer_api_has_explicit_inventory():
    """Record a deterministic provider-to-service consumer inventory for regression review."""
    declared = _provider_factory_names()
    usages: dict[str, set[str]] = {
        path.name: _provider_usage(path)
        for path in _service_files()
        if _provider_usage(path)
    }
    all_used = set().union(*usages.values()) if usages else set()
    assert all_used <= declared
    assert usages, "No RepositoryProvider consumers were discovered."
    assert "students" in all_used, "Core StudentRepository consumer is missing from the discovered surface."


def test_ep_arch_04_5_repository_tree_has_no_application_service_dependency():
    violations: list[str] = []
    for path in _repository_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("centermanager.services"):
                    violations.append(f"{path.name}:{node.lineno}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("centermanager.services"):
                        violations.append(f"{path.name}:{node.lineno}: import {alias.name}")
    assert not violations, "Repositories must not depend upward on application services:\n" + "\n".join(violations)
