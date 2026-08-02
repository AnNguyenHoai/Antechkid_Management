# -*- coding: utf-8 -*-
"""
Business logic services.
"""
from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.student_summary_service import StudentSummaryService
from centermanager.services.student_analytics_service import StudentAnalyticsService
from centermanager.services.exceptions import (
    StudentServiceError,
    StudentNotFoundError,
    StudentValidationError,
    StudentAlreadyDeletedError,
    StudentNotDeletedError,
)
from .session_service import SessionService
from .session_note_service import SessionNoteService

# Teacher
from .teacher_service import TeacherService, TeacherNotFoundError, TeacherValidationError
from .teacher_assignment_service import TeacherAssignmentService
from .teacher_document_service import TeacherDocumentService
from .teacher_timeline_service import TeacherTimelineService

# Class
from .class_service import ClassService, ClassNotFoundError, ClassValidationError, ClassFullError, StudentAlreadyEnrolledError
from .class_timeline_service import ClassTimelineService

# Finance
from .finance_service import FinanceService
from .income_service import IncomeService
from .expense_service import ExpenseService

__all__ = [
    "StudentService",
    "ParentService",
    "TimelineService",
    "AssessmentService",
    "StudentSummaryService",
    "StudentAnalyticsService",
    "StudentServiceError",
    "StudentNotFoundError",
    "StudentValidationError",
    "StudentAlreadyDeletedError",
    "StudentNotDeletedError",
    "TeacherService",
    "TeacherNotFoundError",
    "TeacherValidationError",
    "TeacherAssignmentService",
    "TeacherDocumentService",
    "TeacherTimelineService",
    "ClassService",
    "ClassNotFoundError",
    "ClassValidationError",
    "ClassFullError",
    "StudentAlreadyEnrolledError",
    "ClassTimelineService",
    "FinanceService",
    "IncomeService",
    "ExpenseService",
]