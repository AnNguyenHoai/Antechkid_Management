"""EP-ARCH-04.3 — transaction ownership regression gate."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"

TRANSACTION_METHODS = {"commit", "rollback"}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _transaction_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in TRANSACTION_METHODS
    ]


def test_ep_arch_04_3_repositories_do_not_own_transactions():
    violations: list[str] = []
    for path in sorted(REPOSITORIES.glob("*_repository.py")):
        if path.name in {"base_repository.py", "provider.py"}:
            continue
        for node in _transaction_calls(_parse(path)):
            violations.append(f"{path.name}:{node.lineno}: .{node.func.attr}()")

    assert not violations, (
        "Repository layer must not commit or rollback; transaction ownership belongs "
        "to the application/service boundary: " + ", ".join(violations)
    )


def test_ep_arch_04_3_provider_and_repository_objects_do_not_control_transactions():
    violations: list[str] = []
    for path in sorted(SERVICES.glob("*_service.py")):
        tree = _parse(path)
        for node in _transaction_calls(tree):
            receiver = node.func.value
            if isinstance(receiver, ast.Attribute) and receiver.attr in {
                "_repository_provider",
                "repository_provider",
            }:
                violations.append(f"{path.name}:{node.lineno}: provider.{node.func.attr}()")
            elif isinstance(receiver, ast.Name) and receiver.id in {
                "repo", "repository", "employee_repo", "student_repo", "assessment_repo",
            }:
                violations.append(f"{path.name}:{node.lineno}: {receiver.id}.{node.func.attr}()")

    assert not violations, (
        "Services must not delegate transaction control to repository/provider objects: "
        + ", ".join(violations)
    )


def test_ep_arch_04_3_services_remain_the_transaction_boundary():
    """Guard the intended service-side transaction API without banning reads/queries."""
    transaction_sites = 0
    for path in sorted(SERVICES.glob("*_service.py")):
        for node in _transaction_calls(_parse(path)):
            receiver = node.func.value
            if isinstance(receiver, ast.Name) and receiver.id in {"session", "s"}:
                transaction_sites += 1

    assert transaction_sites > 0, (
        "No service-owned session transaction boundary was detected; "
        "do not silently move transaction ownership into repositories."
    )
