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
from centermanager.repositories.attendance_repository import AttendanceRepository
from centermanager.repositories.class_timeline_repository import ClassTimelineRepository
from centermanager.repositories.enrollment_repository import EnrollmentRepository
from centermanager.repositories.session_repository import SessionRepository


class RepositoryProvider(Protocol):
    """Application-facing factory for persistence adapters."""

    def audit_logs(self, session: Session) -> AuditLogRepository:
        """Return the audit-log repository for ``session``."""
        ...

    def class_timeline(self, session: Session) -> ClassTimelineRepository:
        """Return the class-timeline repository for ``session``."""
        ...

    def attendance(self, session: Session) -> AttendanceRepository:
        """Return the attendance repository for ``session``."""
        ...

    def enrollments(self, session: Session) -> EnrollmentRepository:
        """Return the enrollment repository for ``session``."""
        ...

    def sessions(self, session: Session) -> SessionRepository:
        """Return the session repository for ``session``."""
        ...


class SqlAlchemyRepositoryProvider:
    """Production repository provider backed by SQLAlchemy repositories."""

    def audit_logs(self, session: Session) -> AuditLogRepository:
        return AuditLogRepository(session)

    def class_timeline(self, session: Session) -> ClassTimelineRepository:
        return ClassTimelineRepository(session)

    def attendance(self, session: Session) -> AttendanceRepository:
        return AttendanceRepository(session)

    def enrollments(self, session: Session) -> EnrollmentRepository:
        return EnrollmentRepository(session)

    def sessions(self, session: Session) -> SessionRepository:
        return SessionRepository(session)
