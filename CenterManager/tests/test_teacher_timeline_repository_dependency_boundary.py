from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from centermanager.services.teacher_timeline_service import TeacherTimelineService


SERVICE_PATH = Path(__file__).parents[1] / "src" / "centermanager" / "services" / "teacher_timeline_service.py"


def test_teacher_timeline_service_has_no_concrete_repository_import():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("centermanager.repositories"):
            imports.append(node.module)
    assert imports == ["centermanager.repositories.provider"]


def test_teacher_timeline_service_uses_injected_repository_provider():
    session = MagicMock()
    factory = MagicMock(
        return_value=MagicMock(
            __enter__=MagicMock(return_value=session),
            __exit__=MagicMock(return_value=None),
        )
    )

    repository = MagicMock()
    provider = MagicMock()
    provider.teacher_timeline.return_value = repository

    service = TeacherTimelineService(factory, repository_provider=provider)
    result = service.get_recent_events(limit=3)

    assert result == repository.get_recent_events.return_value
    provider.teacher_timeline.assert_called_once_with(session)
    repository.get_recent_events.assert_called_once_with(limit=3)


def test_teacher_timeline_service_default_provider_is_production_compatible():
    service = TeacherTimelineService(MagicMock())
    assert service._repository_provider.__class__.__name__ == "SqlAlchemyRepositoryProvider"
