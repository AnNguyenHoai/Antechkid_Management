"""EP-ARCH-04.4 — Repository API & Session Encapsulation regression gate."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"
SERVICES = ROOT / "src" / "centermanager" / "services"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _repo_files() -> list[Path]:
    return sorted(REPOSITORIES.glob("*_repository.py"))


def _calls(tree: ast.AST):
    return (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )


def test_ep_arch_04_4_base_repository_does_not_expose_session_accessor():
    base = REPOSITORIES / "base.py"
    assert base.exists(), "Repository base module is required."

    tree = _parse(base)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "session":
            violations.append(f"{base.name}:{node.lineno}: public session accessor")

    assert not violations, (
        "BaseRepository must not expose raw SQLAlchemy Session through a public accessor: "
        + ", ".join(violations)
    )


def test_ep_arch_04_4_services_do_not_access_repository_session():
    violations: list[str] = []
    for path in sorted(SERVICES.glob("*_service.py")):
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or node.attr != "session":
                continue

            receiver = node.value
            if isinstance(receiver, ast.Name) and (
                receiver.id == "repo"
                or receiver.id == "repository"
                or receiver.id.endswith("_repo")
            ):
                violations.append(f"{path.name}:{node.lineno}: {receiver.id}.session")
            elif isinstance(receiver, ast.Attribute) and (
                receiver.attr.endswith("_repository") or receiver.attr == "repository"
            ):
                violations.append(f"{path.name}:{node.lineno}: repository.session")

    assert not violations, (
        "Application services must not recover a raw SQLAlchemy Session from repositories: "
        + ", ".join(violations)
    )


def test_ep_arch_04_4_repositories_do_not_depend_on_application_services():
    violations: list[str] = []
    for path in _repo_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("centermanager.services"):
                    violations.append(f"{path.name}:{node.lineno}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("centermanager.services"):
                        violations.append(f"{path.name}:{node.lineno}: import {alias.name}")

    assert not violations, "Repositories must not depend upward on application services: " + ", ".join(violations)


def test_ep_arch_04_4_repository_public_api_has_no_session_accessor():
    violations: list[str] = []
    for path in _repo_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "session":
                violations.append(f"{path.name}:{node.lineno}: public session() accessor")

    assert not violations, "Repository public APIs must not expose raw Session: " + ", ".join(violations)


def test_ep_arch_04_4_repository_operations_do_not_use_public_session():
    """Prevent repositories from invoking SQLAlchemy operations through a public session attribute."""
    session_operations = {
        "add",
        "delete",
        "execute",
        "get",
        "query",
        "scalar",
        "scalars",
        "flush",
        "refresh",
        "commit",
        "rollback",
    }
    violations: list[str] = []

    for path in _repo_files():
        tree = _parse(path)
        for node in _calls(tree):
            if node.func.attr not in session_operations:
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Attribute) and receiver.attr == "session":
                violations.append(f"{path.name}:{node.lineno}: .session.{node.func.attr}()")

    assert not violations, "Repository persistence must remain behind private session storage: " + ", ".join(violations)


def test_ep_arch_04_4_repository_contract_has_no_transaction_control():
    violations: list[str] = []
    for path in _repo_files():
        tree = _parse(path)
        for node in _calls(tree):
            if node.func.attr in {"commit", "rollback"}:
                violations.append(f"{path.name}:{node.lineno}: .{node.func.attr}()")

    assert not violations, "Repositories must not own commit/rollback: " + ", ".join(violations)
