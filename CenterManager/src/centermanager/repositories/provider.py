# -*- coding: utf-8 -*-
"""Repository dependency boundary for application services.

Services depend on this small provider contract instead of importing concrete
repository implementations. The SQLAlchemy implementation remains the
infrastructure adapter and owns construction of repository objects.
"""
from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from centermanager.repositories.audit_log_repository import AuditLogRepository


class RepositoryProvider(Protocol):
    """Application-facing factory for persistence adapters.

    A provider receives the already-owned transaction/session and returns the
    repository needed by the service. This keeps repository implementation
    selection out of application services while preserving the current
    transaction boundary.
    """

    def audit_logs(self, session: Session) -> AuditLogRepository:
        """Return the audit-log repository for ``session``."""
        ...


class SqlAlchemyRepositoryProvider:
    """Production repository provider backed by SQLAlchemy repositories."""

    def audit_logs(self, session: Session) -> AuditLogRepository:
        return AuditLogRepository(session)
