"""Regression coverage for the StudentService repository boundary."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from centermanager.services.student_service import StudentService


def test_student_service_uses_injected_student_repository_provider():
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session

    student_repo = MagicMock()
    student = MagicMock()
    student.deleted_at = None
    student_repo.get_by_id.return_value = student

    provider = MagicMock()
    provider.students.return_value = student_repo

    service = StudentService(session_factory, repository_provider=provider)

    assert service.get_student(123) is student
    provider.students.assert_called_once_with(session)
    student_repo.get_by_id.assert_called_once_with(123)


def test_student_service_does_not_import_or_construct_concrete_repository():
    path = Path(__file__).parents[1] / "src" / "centermanager" / "services" / "student_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    concrete_imports = []
    concrete_constructors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories.") and module != "centermanager.repositories.provider":
                concrete_imports.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("centermanager.repositories.") and alias.name != "centermanager.repositories.provider":
                    concrete_imports.append(alias.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id.endswith("Repository"):
                concrete_constructors.append(node.func.id)

    assert concrete_imports == []
    assert concrete_constructors == []
