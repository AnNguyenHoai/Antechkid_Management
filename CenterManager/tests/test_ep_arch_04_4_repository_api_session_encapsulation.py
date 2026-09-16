"""EP-ARCH-04.4 — Repository API & Session Encapsulation regression gate.

This test is intentionally source-driven. It discovers the repository tree at
runtime so newly-added repositories cannot silently bypass the contract.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"
SERVICES = ROOT / "src" / "centermanager" / "services"

# Common SQLAlchemy/session primitives which must remain behind repositories.
SESSION_OPERATIONS = {
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


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _attribute_calls(tree: ast.AST):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]


def _repo_files() -> list[Path]:
    return sorted(REPOSITORIES.glob("*_repository.py"))


def test_ep_arch_04_4_base_repository_does_not_expose_session():
    base = REPOSITORIES / "base.py"
    assert base.exists(), "Repository base module is required."
    tree = _parse(base)

    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "session":
            leaks.append(f"{base.name}:{node.lineno}: session member")
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "session":
            leaks.append(f"{base.name}:{node.lineno}: async session member")
        if isinstance(node, ast.Attribute) and node.attr == "session":
            leaks.append(f"{base.name}:{node.lineno}: .session access")

    assert not leaks, "Repository abstraction must not expose raw SQLAlchemy session: " + ", ".join(leaks)


def test_ep_arch_04_4_services_do_not_access_repository_session():
    violations: list[str] = []
    for path in sorted(SERVICES.glob("*_service.py")):
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "session":
                receiver = node.value
                if isinstance(receiver, ast.Name) and (
                    receiver.id in {"repo", "repository", "student_repo", "employee_repo", "assessment_repo"}
                    or receiver.id.endswith("_repo")
                ):
                    violations.append(f"{path.name}:{node.lineno}: {receiver.id}.session")
                elif isinstance(receiver, ast.Attribute) and receiver.attr.endswith("_repository"):
                    violations.append(f"{path.name}:{node.lineno}: repository.session")

    assert not violations, (
        "Application services must not recover a raw SQLAlchemy Session from repositories: "
        + ", ".join(violations)
    )


def test_ep_arch_04_4_repository_modules_do_not_import_application_services():
    violations: list[str] = []
    for path in _repo_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                if module.startswith("centermanager.services"):
                    violations.append(f"{path.name}:{node.lineno}: from {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("centermanager.services"):
                        violations.append(f"{path.name}:{node.lineno}: import {alias.name}")

    assert not violations, "Repositories must not depend upward on application services: " + ", ".join(violations)


def test_ep_arch_04_4_repositories_do_not_expose_session_through_public_api():
    violations: list[str] = []
    for path in _repo_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "session" and not node.name.startswith("_"):
                    violations.append(f"{path.name}:{node.lineno}: public session() method")
                for arg in [*node.args.args, *node.args.kwonlyargs]:
                    if arg.arg in {"session", "db_session"} and node.name == "session":
                        violations.append(f"{path.name}:{node.lineno}: session API")

    assert not violations, "Repository public API must not expose a session accessor: " + ", ".join(violations)


def test_ep_arch_04_4_repository_session_access_is_internal_only():
    violations: list[str] = []
    for path in _repo_files():
        tree = _parse(path)
        for node in _attribute_calls(tree):
            if node.func.attr in SESSION_OPERATIONS:
                receiver = node.func.value
                if not (
                    isinstance(receiver, ast.Attribute)
                    and receiver.attr in {"_session", "session"}
                ):
                    continue
                if isinstance(receiver, ast.Attribute) and receiver.attr == "session":
                    # A repository should use its private session storage, not expose a session property.
                    violations.append(f"{path.name}:{node.lineno}: public .session.{node.func.attr}()")

    assert not violations, "Repository implementation must keep raw Session access behind a private member: " + ", ".join(violations)


def test_ep_arch_04_4_repository_contract_has_no_transaction_control():
    """Keep transaction ownership enforced by EP-ARCH-04.3 without duplicating its implementation gate."""
    violations: list[str] = []
    for path in _repo_files():
        tree = _parse(path)
        for node in _attribute_calls(tree):
            if node.func.attr in {"commit", "rollback"}:
                violations.append(f"{path.name}:{node.lineno}: .{node.func.attr}()")

    assert not violations, "Repositories must not own commit/rollback: " + ", ".join(violations)
