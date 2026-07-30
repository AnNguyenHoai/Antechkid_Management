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
from centermanager.models.teacher import Teacher
from centermanager.models.user import User
from centermanager.repositories.student_repository import StudentRepository
from centermanager.repositories.timeline_repository import TimelineRepository
from centermanager.repositories.assessment_repository import AssessmentRepository
from centermanager.repositories.parent_repository import ParentRepository
from centermanager.repositories.session_repository import SessionRepository
from centermanager.core.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceSummary:
    workspace_id: str
    name: str
    icon: str
    description: str
    summary_text: str
    health_status: str
    health_details: str
    quick_action_label: str
    quick_action_target: str


@dataclass
class RecentActivity:
    workspace_id: str
    icon: str
    title: str
    student_name: str
    student_code: str
    time: datetime
    activity_type: str


@dataclass
class TodaySummary:
    today_classes: int
    today_assessments: int
    today_birthdays: List[str]
    pending_tasks: List[str]
    upcoming_sessions: int


@dataclass
class SystemStatus:
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

            class_count = session.query(Class).count()
            session_count = session.query(Session).filter(Session.status == "Scheduled").count()
            teacher_count = session.query(Teacher).count()
            teacher_ws = WorkspaceSummary(
                workspace_id="teacher",
                name="Teacher Workspace",
                icon="👨‍🏫",
                description="Teaching activities and classes",
                summary_text=f"{teacher_count} teachers, {class_count} classes, {session_count} upcoming sessions",
                health_status="good",
                health_details="",
                quick_action_label="Open →",
                quick_action_target="teacher"
            )

            class_ws = WorkspaceSummary(
                workspace_id="class",
                name="Class Workspace",
                icon="📚",
                description="Manage classes, enrollments, schedules",
                summary_text=f"{class_count} classes",
                health_status="good",
                health_details="",
                quick_action_label="Open →",
                quick_action_target="class"
            )

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

            return [student_ws, teacher_ws, class_ws, finance_ws]

    def get_recent_activities(self, limit: int = 10) -> List[RecentActivity]:
        try:
            with self._session_factory() as session:
                events = session.query(TimelineEvent).order_by(
                    TimelineEvent.created_at.desc()
                ).limit(limit).all()
                activities = []
                for ev in events:
                    student = ev.student
                    workspace_id = "student"
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
        except Exception as e:
            logger.exception("Failed to get recent activities")
            return []

    def get_today_summary(self) -> TodaySummary:
        today = date.today()
        with self._session_factory() as session:
            today_sessions = session.query(Session).filter(
                Session.scheduled_date == today,
                Session.status == "Scheduled"
            ).count()
            today_assessments = session.query(Assessment).filter(
                Assessment.assessment_date == today
            ).count()
            students = session.query(Student).all()
            birthdays = []
            for s in students:
                if s.date_of_birth and s.date_of_birth.month == today.month and s.date_of_birth.day == today.day:
                    birthdays.append(s.full_name)
            week_later = today + timedelta(days=7)
            upcoming = session.query(Session).filter(
                Session.scheduled_date > today,
                Session.scheduled_date <= week_later,
                Session.status == "Scheduled"
            ).count()

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
            pending_tasks = pending[:5]

            return TodaySummary(
                today_classes=today_sessions,
                today_assessments=today_assessments,
                today_birthdays=birthdays,
                pending_tasks=pending_tasks,
                upcoming_sessions=upcoming
            )

    def get_system_status(self) -> SystemStatus:
        config = get_config()
        version = config.get("application.version", "0.1.0")
        return SystemStatus(
            database_status="Online",
            version=version,
            last_backup="Never",
            current_user="Admin",
            environment="Development"
        )