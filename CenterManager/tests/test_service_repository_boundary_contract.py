"""Architecture guard for the EP-ARCH-03 service/repository boundary."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = PROJECT_ROOT / "src" / "centermanager" / "services"

MIGRATED_SERVICES = (
    "audit_service.py",
    "attendance_service.py",
    "class_timeline_service.py",
    "class_service.py",
    "employee_schedule_service.py",
    "employee_admin_management_service.py",
    "employee_document_service.py",
    "employee_service.py",
    "enrollment_service.py",
    "expense_timeline_service.py",
    "income_service.py",
    "teacher_assignment_service.py",
    "teacher_service.py",
    "student_note_service.py",
    "student_service.py",
)


class _BoundaryVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.repository_imports: list[str] = []
        self.provider_imports: list[str] = []
        self.concrete_constructors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.startswith("centermanager.repositories"):
                self.repository_imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module.startswith("centermanager.repositories"):
            if module == "centermanager.repositories.provider":
                self.provider_imports.extend(alias.name for alias in node.names)
            else:
                self.repository_imports.append(module)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
            self.concrete_constructors.append(node.func.id)
        elif isinstance(node.func, ast.Attribute) and node.func.attr.endswith("Repository"):
            self.concrete_constructors.append(node.func.attr)
        self.generic_visit(node)


@pytest.mark.parametrize("filename", MIGRATED_SERVICES)
def test_migrated_services_depend_on_repository_provider_only(filename: str) -> None:
    source_path = SERVICES_DIR / filename
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    visitor = _BoundaryVisitor()
    visitor.visit(tree)

    assert not visitor.repository_imports, (
        f"{filename} bypasses RepositoryProvider with concrete repository imports: "
        f"{visitor.repository_imports}"
    )
    assert "RepositoryProvider" in visitor.provider_imports, (
        f"{filename} must depend on RepositoryProvider"
    )
    assert not visitor.concrete_constructors, (
        f"{filename} constructs concrete repositories directly: {visitor.concrete_constructors}"
    )


def test_repository_provider_is_the_application_facing_repository_factory() -> None:
    provider_path = PROJECT_ROOT / "src" / "centermanager" / "repositories" / "provider.py"
    tree = ast.parse(provider_path.read_text(encoding="utf-8"), filename=str(provider_path))
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert "RepositoryProvider" in classes
    assert "SqlAlchemyRepositoryProvider" in classes


def test_migration_guard_has_no_duplicate_service_allowlist_entries() -> None:
    assert len(MIGRATED_SERVICES) == len(set(MIGRATED_SERVICES))
    assert all(filename.endswith("_service.py") for filename in MIGRATED_SERVICES)
