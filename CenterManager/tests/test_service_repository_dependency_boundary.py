from __future__ import annotations

from unittest.mock import MagicMock

from centermanager.services.audit_service import AuditService


class _FakeAuditRepository:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.received_filters = None

    def search(self, **filters):
        self.received_filters = filters
        return self.rows


class _FakeRepositoryProvider:
    def __init__(self, repository):
        self.repository = repository
        self.received_session = None

    def audit_logs(self, session):
        self.received_session = session
        return self.repository


def test_audit_service_uses_injected_repository_provider():
    session = MagicMock()
    factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=session), __exit__=MagicMock(return_value=None)))
    repository = _FakeAuditRepository(["audit-row"])
    provider = _FakeRepositoryProvider(repository)

    service = AuditService(factory, repository_provider=provider)

    assert service.list_logs(action="student.updated") == ["audit-row"]
    assert provider.received_session is session
    assert repository.received_filters == {"action": "student.updated"}


def test_audit_service_default_provider_remains_production_compatible():
    """The boundary must not require callers to change during migration."""
    service = AuditService(MagicMock())

    assert service._repository_provider.__class__.__name__ == "SqlAlchemyRepositoryProvider"
