# -*- coding: utf-8 -*-
"""
SQLAlchemy ORM models.
"""
from centermanager.models.student import Student
from centermanager.models.parent import Parent
from centermanager.models.enrollment import Enrollment
from centermanager.models.assessment import Assessment
from centermanager.models.timeline_event import TimelineEvent
from centermanager.models.student_product import StudentProduct
from centermanager.models.progress import Progress
from centermanager.models.attachment import Attachment
from centermanager.models.class_ import Class
from centermanager.models.session import Session, SessionStatus
from centermanager.models.session_note import SessionNote, TeachingProgress, ClassAtmosphere
from centermanager.models.student_highlight import StudentHighlight, HighlightType
from centermanager.models.note import Note, NoteType
from centermanager.models.document import Document
from centermanager.models.report import Report  # NEW
from centermanager.models.report_cache import ReportCache
# RBAC Models
from centermanager.models.user import User
from centermanager.models.role import Role, RoleDefinitions
from centermanager.models.permission import Permission, PermissionDefinitions
from centermanager.models.role_permission import RolePermission

# Teacher
from centermanager.models.teacher import Teacher
from centermanager.models.teacher_document import TeacherDocument
from centermanager.models.teacher_timeline_event import TeacherTimelineEvent, TeacherTimelineEventType
from centermanager.models.teacher_assignment import TeacherAssignment

# Class Timeline
from centermanager.models.class_timeline_event import ClassTimelineEvent, ClassTimelineEventType

# Finance
from centermanager.models.income import Income
from centermanager.models.expense import Expense
from centermanager.models.expense_timeline_event import ExpenseTimelineEvent
from centermanager.models.attendance import Attendance, AttendanceStatus

__all__ = [
    "Student",
    "Parent",
    "Enrollment",
    "Assessment",
    "TimelineEvent",
    "StudentProduct",
    "Progress",
    "Attachment",
    "Class",
    "Session",
    "SessionStatus",
    "SessionNote",
    "TeachingProgress",
    "ClassAtmosphere",
    "StudentHighlight",
    "HighlightType",
    "Note",
    "NoteType",
    "Document",
    "Report",  # NEW
    "User",
    "Role",
    "RoleDefinitions",
    "Permission",
    "PermissionDefinitions",
    "RolePermission",
    "Teacher",
    "TeacherDocument",
    "TeacherTimelineEvent",
    "TeacherTimelineEventType",
    "TeacherAssignment",
    "ClassTimelineEvent",
    "ClassTimelineEventType",
    "Income",
    "Expense",
    "ExpenseTimelineEvent",
    "Attendance",
    "AttendanceStatus",
    "ReportCache",
]