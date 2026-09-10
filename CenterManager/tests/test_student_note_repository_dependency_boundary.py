"""Regression coverage for the StudentNoteService repository boundary."""
from __future__ import annotations

from unittest.mock import MagicMock

from centermanager.services.student_note_service import StudentNoteService


def test_student_note_service_uses_injected_note_repository_provider():
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session

    note_repo = MagicMock()
    note = MagicMock()
    note_repo.get_by_id.return_value = note

    provider = MagicMock()
    provider.notes.return_value = note_repo

    service = StudentNoteService(session_factory, repository_provider=provider)

    assert service.get_note_by_id(11) is note
    provider.notes.assert_called_once_with(session)
    note_repo.get_by_id.assert_called_once_with(11)


def test_student_note_service_does_not_import_concrete_repository():
    import ast
    from pathlib import Path

    path = Path(__file__).parents[1] / "src" / "centermanager" / "services" / "student_note_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    # RepositoryProvider is the explicit application-facing dependency seam.
    # Only concrete repository implementations are forbidden here.
    concrete_repository_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories.") and module != "centermanager.repositories.provider":
                concrete_repository_imports.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if module.startswith("centermanager.repositories.") and module != "centermanager.repositories.provider":
                    concrete_repository_imports.append(module)

    assert concrete_repository_imports == []
