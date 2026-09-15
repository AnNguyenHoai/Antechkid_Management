from __future__ import annotations

from unittest.mock import MagicMock

from centermanager.services.class_timeline_service import ClassTimelineService


class _FakeClassTimelineRepository:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.added = None
        self.received_limit = None

    def add(self, event):
        self.added = event

    def get_by_class(self, class_id, limit=None):
        self.received_limit = (class_id, limit)
        return self.rows


class _FakeRepositoryProvider:
    def __init__(self, repository):
        self.repository = repository
        self.received_session = None

    def class_timeline(self, session):
        self.received_session = session
        return self.repository


def _session_factory(session):
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = None
    return MagicMock(return_value=context)


def test_class_timeline_service_uses_injected_repository_provider():
    session = MagicMock()
    repository = _FakeClassTimelineRepository(["timeline-row"])
    provider = _FakeRepositoryProvider(repository)
    service = ClassTimelineService(_session_factory(session), repository_provider=provider)

    assert service.get_class_timeline(42, limit=10) == ["timeline-row"]
    assert provider.received_session is session
    assert repository.received_limit == (42, 10)


def test_class_timeline_service_default_provider_remains_compatible():
    service = ClassTimelineService(MagicMock())

    assert service._repository_provider.__class__.__name__ == "SqlAlchemyRepositoryProvider"
