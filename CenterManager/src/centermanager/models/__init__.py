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
from centermanager.models.session import Session
from centermanager.models.session_note import SessionNote
from centermanager.models.student_highlight import StudentHighlight, HighlightType
from centermanager.models.note import Note, NoteType
from centermanager.models.document import Document

# RBAC Models
from centermanager.models.user import User
from centermanager.models.role import Role, RoleDefinitions
from centermanager.models.permission import Permission, PermissionDefinitions
from centermanager.models.role_permission import RolePermission
# Thêm các import mới
from centermanager.models.teacher import Teacher
from centermanager.models.teacher_document import TeacherDocument
from centermanager.models.teacher_timeline_event import TeacherTimelineEvent, TeacherTimelineEventType
from centermanager.models.teacher_assignment import TeacherAssignment

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
    "SessionNote",
    "StudentHighlight",
    "HighlightType",
    "Note",
    "NoteType",
    "Document",
    "User",
    "Role",
    "RoleDefinitions",
    "Permission",
    "PermissionDefinitions",
    "RolePermission",
]