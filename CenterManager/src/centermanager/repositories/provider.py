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
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_schedule_repository import EmployeeScheduleRepository
from centermanager.repositories.class_repository import ClassRepository
from centermanager.repositories.student_repository import StudentRepository
from centermanager.repositories.teacher_timeline_repository import TeacherTimelineRepository


class RepositoryProvider(Protocol):
    """Application-facing factory for persistence adapters."""

    def audit_logs(self, session: Session) -> AuditLogRepository:
        ...

    def class_timeline(self, session: Session) -> ClassTimelineRepository:
        ...

    def attendance(self, session: Session) -> AttendanceRepository:
        ...

    def enrollments(self, session: Session) -> EnrollmentRepository:
        ...

    def sessions(self, session: Session) -> SessionRepository:
        ...

    def employees(self, session: Session) -> EmployeeRepository:
        ...

    def employee_schedules(self, session: Session) -> EmployeeScheduleRepository:
        ...

    def classes(self, session: Session) -> ClassRepository:
        ...

    def students(self, session: Session) -> StudentRepository:
        ...

    def teacher_timeline(self, session: Session) -> TeacherTimelineRepository:
        """Return the teacher-timeline repository for ``session``."""
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

    def employees(self, session: Session) -> EmployeeRepository:
        return EmployeeRepository(session)

    def employee_schedules(self, session: Session) -> EmployeeScheduleRepository:
        return EmployeeScheduleRepository(session)

    def classes(self, session: Session) -> ClassRepository:
        return ClassRepository(session)

    def students(self, session: Session) -> StudentRepository:
        return StudentRepository(session)

    def teacher_timeline(self, session: Session) -> TeacherTimelineRepository:
        return TeacherTimelineRepository(session)
