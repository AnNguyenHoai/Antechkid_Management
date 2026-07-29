# -*- coding: utf-8 -*-
"""
HomeDashboardService - provides aggregated data for Home Workspace (Command Center).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.student import Student
from centermanager.models.timeline_event import TimelineEvent
from centermanager.models.assessment import Assessment
from centermanager.models.parent import Parent
from centermanager.models.class_ import Class
from centermanager.models.session import Session
from centermanager.repositories.student_repository import StudentRepository
from centermanager.repositories.timeline_repository import TimelineRepository
from centermanager.repositories.assessment_repository import AssessmentRepository
from centermanager.repositories.parent_repository import ParentRepository
from centermanager.repositories.session_repository import SessionRepository
from centermanager.core.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceSummary:
    """Summary for a workspace card."""
    workspace_id: str
    name: str
    icon: str
    description: str
    summary_text: str
    health_status: str  # "good", "warning", "critical"
    health_details: str
    quick_action_label: str
    quick_action_target: str  # e.g., "student" to open student workspace


@dataclass
class RecentActivity:
    """Recent activity across all workspaces."""
    workspace_id: str
    icon: str
    title: str
    student_name: str
    student_code: str
    time: datetime
    activity_type: str  # e.g., "StudentCreated", "AssessmentCreated", etc.


@dataclass
class TodaySummary:
    """Today's summary panel."""
    today_classes: int
    today_assessments: int
    today_birthdays: List[str]  # list of student names
    pending_tasks: List[str]  # placeholder
    upcoming_sessions: int


@dataclass
class SystemStatus:
    """System status panel."""
    database_status: str
    version: str
    last_backup: str
    current_user: str
    environment: str


class HomeDashboardService:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def get_workspace_summaries(self) -> List[WorkspaceSummary]:
        with self._session_factory() as session:
            student_repo = StudentRepository(session)
            parent_repo = ParentRepository(session)
            assessment_repo = AssessmentRepository(session)

            # Student workspace summary
            total_students = len(student_repo.list_active())
            parent_count = session.query(Parent).count()
            assessment_count = session.query(Assessment).count()
            students_without_parent = 0
            students_without_assessment = 0
            active_students = student_repo.list_active()
            for s in active_students:
                if not parent_repo.get_by_student(s.id):
                    students_without_parent += 1
                if not assessment_repo.get_by_student(s.id):
                    students_without_assessment += 1
            health_status = "good"
            health_details = ""
            if students_without_parent > 0 or students_without_assessment > 0:
                health_status = "warning"
                parts = []
                if students_without_parent > 0:
                    parts.append(f"{students_without_parent} missing parent")
                if students_without_assessment > 0:
                    parts.append(f"{students_without_assessment} no assessment")
                health_details = "; ".join(parts)
            summary_text = f"{total_students} students, {parent_count} parents, {assessment_count} assessments"
            student_ws = WorkspaceSummary(
                workspace_id="student",
                name="Student Workspace",
                icon="👨‍🎓",
                description="Manage students, parents, assessments",
                summary_text=summary_text,
                health_status=health_status,
                health_details=health_details,
                quick_action_label="Open →",
                quick_action_target="student"
            )

            # Teacher workspace summary
            class_count = session.query(Class).count()
            session_count = session.query(Session).filter(Session.status == "Scheduled").count()
            teacher_ws = WorkspaceSummary(
                workspace_id="teacher",
                name="Teacher Workspace",
                icon="👨‍🏫",
                description="Teaching activities and classes",
                summary_text=f"{class_count} classes, {session_count} upcoming sessions",
                health_status="good",
                health_details="",
                quick_action_label="Open →",
                quick_action_target="teacher"
            )

            # Finance workspace summary (placeholder)
            finance_ws = WorkspaceSummary(
                workspace_id="finance",
                name="Finance Workspace",
                icon="💰",
                description="Invoices, payments, revenue",
                summary_text="Revenue: $0, Outstanding: $0",
                health_status="good",
                health_details="",
                quick_action_label="Open →",
                quick_action_target="finance"
            )

            # Chỉ trả về các Workspace Business Domain
            return [student_ws, teacher_ws, finance_ws]

    def get_recent_activities(self, limit: int = 10) -> List[RecentActivity]:
        """Get recent activities across all workspaces."""
        with self._session_factory() as session:
            events = session.query(TimelineEvent).order_by(
                TimelineEvent.created_at.desc()
            ).limit(limit).all()
            activities = []
            for ev in events:
                student = ev.student
                workspace_id = "student"  # currently all timeline events are student-related
                icon_map = {
                    "StudentCreated": "🌟",
                    "StudentUpdated": "✏️",
                    "ParentAdded": "👨‍👩‍👧",
                    "ParentUpdated": "✏️",
                    "ParentDeleted": "🗑️",
                    "AssessmentCreated": "📊",
                    "AssessmentUpdated": "✏️",
                    "AssessmentDeleted": "🗑️",
                    "ProductAdded": "📁",
                    "AttachmentAdded": "📎",
                    "System": "⚙️",
                }
                icon = icon_map.get(ev.event_type, "📌")
                activities.append(RecentActivity(
                    workspace_id=workspace_id,
                    icon=icon,
                    title=ev.title,
                    student_name=student.full_name if student else "Unknown",
                    student_code=student.student_code if student else "",
                    time=ev.created_at,
                    activity_type=ev.event_type
                ))
            return activities

    def get_today_summary(self) -> TodaySummary:
        """Get today's summary."""
        today = date.today()
        with self._session_factory() as session:
            # Today's classes (sessions scheduled today)
            today_sessions = session.query(Session).filter(
                Session.scheduled_date == today,
                Session.status == "Scheduled"
            ).count()
            # Today's assessments (assessments created today)
            today_assessments = session.query(Assessment).filter(
                Assessment.assessment_date == today
            ).count()
            # Today's birthdays (students with DOB month/day = today)
            students = session.query(Student).all()
            birthdays = []
            for s in students:
                if s.date_of_birth and s.date_of_birth.month == today.month and s.date_of_birth.day == today.day:
                    birthdays.append(s.full_name)
            # Upcoming sessions (next 7 days)
            week_later = today + timedelta(days=7)
            upcoming = session.query(Session).filter(
                Session.scheduled_date > today,
                Session.scheduled_date <= week_later,
                Session.status == "Scheduled"
            ).count()

            # Pending tasks: students without parent or assessment (for now)
            student_repo = StudentRepository(session)
            parent_repo = ParentRepository(session)
            assessment_repo = AssessmentRepository(session)
            pending = []
            active_students = student_repo.list_active()
            for s in active_students:
                if not parent_repo.get_by_student(s.id):
                    pending.append(f"{s.full_name} missing parent")
                elif not assessment_repo.get_by_student(s.id):
                    pending.append(f"{s.full_name} no assessment")
            pending_tasks = pending[:5]  # limit

            return TodaySummary(
                today_classes=today_sessions,
                today_assessments=today_assessments,
                today_birthdays=birthdays,
                pending_tasks=pending_tasks,
                upcoming_sessions=upcoming
            )

    def get_system_status(self) -> SystemStatus:
        """Get system status."""
        config = get_config()
        version = config.get("application.version", "0.1.0")
        return SystemStatus(
            database_status="Online",
            version=version,
            last_backup="Never",
            current_user="Admin",
            environment="Development"
        )