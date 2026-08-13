# -*- coding: utf-8 -*-
"""HomeDashboardService - provides aggregated data for Home Workspace."""
import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.student import Student
from centermanager.models.parent import Parent
from centermanager.models.assessment import Assessment
from centermanager.models.class_ import Class
from centermanager.models.session import Session
from centermanager.models.teacher import Teacher
from centermanager.repositories.student_repository import StudentRepository
from centermanager.repositories.parent_repository import ParentRepository
from centermanager.repositories.assessment_repository import AssessmentRepository
from centermanager.core.current_user import get_current_user
from centermanager.models.user import User

# === THÊM IMPORT ===
from centermanager.events.student_events import StudentArchived, StudentActivated, StudentDeleted
from centermanager.events.event_bus import EventBus

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


class HomeDashboardService:
    def __init__(self, session_factory: sessionmaker, event_bus: Optional[EventBus] = None):
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._cache = None
        self._cache_invalidated = True
        
        # Register event listeners
        if event_bus:
            event_bus.register(StudentArchived, self._on_student_archived)
            event_bus.register(StudentActivated, self._on_student_activated)
            event_bus.register(StudentDeleted, self._on_student_deleted)
            logger.info("HomeDashboardService registered for student events")
    
    def _on_student_archived(self, event: StudentArchived) -> None:
        self._cache_invalidated = True
        logger.info(f"Cache invalidated: student {event.student_id} archived")
    
    def _on_student_activated(self, event: StudentActivated) -> None:
        self._cache_invalidated = True
        logger.info(f"Cache invalidated: student {event.student_id} activated")
    
    def _on_student_deleted(self, event: StudentDeleted) -> None:
        self._cache_invalidated = True
        logger.info(f"Cache invalidated: student {event.student_id} deleted")

    def get_workspace_summaries(self) -> List[WorkspaceSummary]:
        """Get workspace summaries with caching."""
        if not self._cache_invalidated and self._cache is not None:
            return self._cache
        
        with self._session_factory() as session:
            student_repo = StudentRepository(session)
            parent_repo = ParentRepository(session)
            assessment_repo = AssessmentRepository(session)

            all_students = student_repo.list_all_including_deleted()
            total_students = len(all_students)
            
            # Đếm active và archived dựa trên status, không chỉ deleted_at
            active_count = 0
            archived_count = 0
            for s in all_students:
                if s.deleted_at is not None:
                    continue
                if s.status == "ARCHIVED":
                    archived_count += 1
                else:
                    active_count += 1
            
            parent_count = session.query(Parent).count()
            assessment_count = session.query(Assessment).count()
            
            # Chỉ lấy active students để tính thiếu parent/assessment
            active_students = session.query(Student).filter(
                Student.deleted_at.is_(None),
                Student.status != "ARCHIVED"
            ).all()
            
            students_without_parent = 0
            students_without_assessment = 0
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

            summaries = []

            # Student Workspace - always visible
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
            summaries.append(student_ws)

            # Teacher Workspace
            class_count = session.query(Class).count()
            session_count = session.query(Session).filter(Session.status == "Scheduled").count()
            teacher_count = session.query(Teacher).count()

            user = get_current_user()
            if user and (user.has_permission("teacher.view") or user.is_admin):
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
                summaries.append(teacher_ws)

            # Class Workspace
            if user and (user.has_permission("class.view") or user.is_admin):
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
                summaries.append(class_ws)

            # Finance Workspace
            if user and (user.has_permission("finance.view") or user.is_admin):
                from centermanager.services.outstanding_service import OutstandingService
                outstanding_service = OutstandingService(self._session_factory)
                stats = outstanding_service.get_outstanding_stats()
                revenue = stats.get('total_paid', 0)
                outstanding = stats.get('total_outstanding', 0)

                finance_ws = WorkspaceSummary(
                    workspace_id="finance",
                    name="Finance Workspace",
                    icon="💰",
                    description="Invoices, payments, revenue",
                    summary_text=f"Revenue: {revenue:,.0f} VND, Outstanding: {outstanding:,.0f} VND",
                    health_status="good",
                    health_details="",
                    quick_action_label="Open →",
                    quick_action_target="finance"
                )
                summaries.append(finance_ws)

            # Admin Workspace
            if user and (user.has_permission("user.manage") or user.is_admin):
                admin_ws = WorkspaceSummary(
                    workspace_id="admin",
                    name="Admin Workspace",
                    icon="⚙️",
                    description="User management and system settings",
                    summary_text="Manage users and configuration",
                    health_status="good",
                    health_details="",
                    quick_action_label="Open →",
                    quick_action_target="admin"
                )
                summaries.append(admin_ws)

            self._cache = summaries
            self._cache_invalidated = False
            logger.info(f"HomeDashboard cache updated: total={total_students}, active={active_count}, archived={archived_count}")
            return summaries

    def refresh(self) -> None:
        """Force refresh cache."""
        self._cache_invalidated = True