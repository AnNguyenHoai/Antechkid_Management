# -*- coding: utf-8 -*-
"""Data access layer (Repository pattern)."""
from centermanager.repositories.base import BaseRepository
from centermanager.repositories.student_repository import StudentRepository
from .session_repository import SessionRepository
from .session_note_repository import SessionNoteRepository
from .student_highlight_repository import StudentHighlightRepository
from .enrollment_repository import EnrollmentRepository
from .class_repository import ClassRepository
from .note_repository import NoteRepository
from .document_repository import DocumentRepository

# RBAC Repositories
from .user_repository import UserRepository
from .role_repository import RoleRepository
from .permission_repository import PermissionRepository

# Teacher
from .teacher_repository import TeacherRepository
from .teacher_document_repository import TeacherDocumentRepository
from .teacher_timeline_repository import TeacherTimelineRepository
from .teacher_assignment_repository import TeacherAssignmentRepository

# Class Timeline
from .class_timeline_repository import ClassTimelineRepository

# Finance
from .income_repository import IncomeRepository
from .expense_repository import ExpenseRepository
from .expense_timeline_repository import ExpenseTimelineRepository
from .attendance_repository import AttendanceRepository

__all__ = [
    "BaseRepository",
    "StudentRepository",
    "SessionRepository",
    "SessionNoteRepository",
    "StudentHighlightRepository",
    "EnrollmentRepository",
    "ClassRepository",
    "NoteRepository",
    "DocumentRepository",
    "UserRepository",
    "RoleRepository",
    "PermissionRepository",
    "TeacherRepository",
    "TeacherDocumentRepository",
    "TeacherTimelineRepository",
    "TeacherAssignmentRepository",
    "ClassTimelineRepository",
    "IncomeRepository",
    "ExpenseRepository",
    "ExpenseTimelineRepository",
    "AttendanceRepository",
]