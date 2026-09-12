# -*- coding: utf-8 -*-
"""Repository dependency boundary for application services."""
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
from centermanager.repositories.employee_work_registration_period_repository import EmployeeWorkRegistrationPeriodRepository
from centermanager.repositories.employee_work_registration_repository import EmployeeWorkRegistrationRepository
from centermanager.repositories.employee_document_repository import EmployeeDocumentRepository
from centermanager.repositories.class_repository import ClassRepository
from centermanager.repositories.student_repository import StudentRepository
from centermanager.repositories.assessment_repository import AssessmentRepository
from centermanager.repositories.report_repository import ReportRepository
from centermanager.repositories.expense_repository import ExpenseRepository
from centermanager.repositories.expense_timeline_repository import ExpenseTimelineRepository
from centermanager.repositories.income_repository import IncomeRepository
from centermanager.repositories.teacher_repository import TeacherRepository
from centermanager.repositories.teacher_assignment_repository import TeacherAssignmentRepository
from centermanager.repositories.teacher_document_repository import TeacherDocumentRepository
from centermanager.repositories.note_repository import NoteRepository
from centermanager.repositories.user_repository import UserRepository
from centermanager.repositories.role_repository import RoleRepository
from centermanager.repositories.permission_repository import PermissionRepository
from centermanager.repositories.employee_working_time_repository import EmployeeWorkingTimeRepository
from centermanager.repositories.parent_repository import ParentRepository


class RepositoryProvider(Protocol):
    """Application-facing factory for persistence adapters."""
    def audit_logs(self, session: Session) -> AuditLogRepository: ...
    def class_timeline(self, session: Session) -> ClassTimelineRepository: ...
    def attendance(self, session: Session) -> AttendanceRepository: ...
    def enrollments(self, session: Session) -> EnrollmentRepository: ...
    def sessions(self, session: Session) -> SessionRepository: ...
    def employees(self, session: Session) -> EmployeeRepository: ...
    def users(self, session: Session) -> UserRepository: ...
    def roles(self, session: Session) -> RoleRepository: ...
    def permissions(self, session: Session) -> PermissionRepository: ...
    def employee_schedules(self, session: Session) -> EmployeeScheduleRepository: ...
    def employee_work_registration_periods(self, session: Session) -> EmployeeWorkRegistrationPeriodRepository: ...
    def employee_work_registrations(self, session: Session) -> EmployeeWorkRegistrationRepository: ...
    def employee_working_times(self, session: Session) -> EmployeeWorkingTimeRepository: ...
    def employee_documents(self, session: Session) -> EmployeeDocumentRepository: ...
    def classes(self, session: Session) -> ClassRepository: ...
    def students(self, session: Session) -> StudentRepository: ...
    def assessments(self, session: Session) -> AssessmentRepository: ...
    def reports(self, session: Session) -> ReportRepository: ...
    def expenses(self, session: Session) -> ExpenseRepository: ...
    def expense_timeline(self, session: Session) -> ExpenseTimelineRepository: ...
    def incomes(self, session: Session) -> IncomeRepository: ...
    def teachers(self, session: Session) -> TeacherRepository: ...
    def teacher_assignments(self, session: Session) -> TeacherAssignmentRepository: ...
    def teacher_documents(self, session: Session) -> TeacherDocumentRepository: ...
    def notes(self, session: Session) -> NoteRepository: ...
    def parents(self, session: Session) -> ParentRepository: ...


class SqlAlchemyRepositoryProvider:
    """Production repository provider backed by SQLAlchemy repositories."""
    def audit_logs(self, session: Session) -> AuditLogRepository: return AuditLogRepository(session)
    def class_timeline(self, session: Session) -> ClassTimelineRepository: return ClassTimelineRepository(session)
    def attendance(self, session: Session) -> AttendanceRepository: return AttendanceRepository(session)
    def enrollments(self, session: Session) -> EnrollmentRepository: return EnrollmentRepository(session)
    def sessions(self, session: Session) -> SessionRepository: return SessionRepository(session)
    def employees(self, session: Session) -> EmployeeRepository: return EmployeeRepository(session)
    def users(self, session: Session) -> UserRepository: return UserRepository(session)
    def roles(self, session: Session) -> RoleRepository: return RoleRepository(session)
    def permissions(self, session: Session) -> PermissionRepository: return PermissionRepository(session)
    def employee_schedules(self, session: Session) -> EmployeeScheduleRepository: return EmployeeScheduleRepository(session)
    def employee_work_registration_periods(self, session: Session) -> EmployeeWorkRegistrationPeriodRepository: return EmployeeWorkRegistrationPeriodRepository(session)
    def employee_work_registrations(self, session: Session) -> EmployeeWorkRegistrationRepository: return EmployeeWorkRegistrationRepository(session)
    def employee_working_times(self, session: Session) -> EmployeeWorkingTimeRepository: return EmployeeWorkingTimeRepository(session)
    def employee_documents(self, session: Session) -> EmployeeDocumentRepository: return EmployeeDocumentRepository(session)
    def classes(self, session: Session) -> ClassRepository: return ClassRepository(session)
    def students(self, session: Session) -> StudentRepository: return StudentRepository(session)
    def assessments(self, session: Session) -> AssessmentRepository: return AssessmentRepository(session)
    def reports(self, session: Session) -> ReportRepository: return ReportRepository(session)
    def expenses(self, session: Session) -> ExpenseRepository: return ExpenseRepository(session)
    def expense_timeline(self, session: Session) -> ExpenseTimelineRepository: return ExpenseTimelineRepository(session)
    def incomes(self, session: Session) -> IncomeRepository: return IncomeRepository(session)
    def teachers(self, session: Session) -> TeacherRepository: return TeacherRepository(session)
    def teacher_assignments(self, session: Session) -> TeacherAssignmentRepository: return TeacherAssignmentRepository(session)
    def teacher_documents(self, session: Session) -> TeacherDocumentRepository: return TeacherDocumentRepository(session)
    def notes(self, session: Session) -> NoteRepository: return NoteRepository(session)
    def parents(self, session: Session) -> ParentRepository: return ParentRepository(session)


def create_default_repository_provider() -> RepositoryProvider:
    """Create the production provider for legacy callers during migration."""
    return SqlAlchemyRepositoryProvider()
