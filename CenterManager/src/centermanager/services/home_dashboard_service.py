# -*- coding: utf-8 -*-
"""HomeDashboardService - provides aggregated data for Home Workspace."""
import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.core.current_user import get_current_user
from centermanager.models.user import User
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
    def __init__(self, session_factory: sessionmaker, event_bus: Optional[EventBus] = None,
                 repository_provider: Optional[RepositoryProvider] = None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._event_bus = event_bus
        self._cache = None
        self._cache_invalidated = True
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
            student_repo = self._repository_provider.students(session)
            parent_repo = self._repository_provider.parents(session)
            assessment_repo = self._repository_provider.assessments(session)
            class_repo = self._repository_provider.classes(session)
            session_repo = self._repository_provider.sessions(session)
            teacher_repo = self._repository_provider.teachers(session)
            employee_repo = self._repository_provider.employees(session)

            all_students = student_repo.list_all_including_deleted()
            total_students = len(all_students)
            active_count = 0
            archived_count = 0
            for student in all_students:
                if student.deleted_at is not None:
                    continue
                if student.status == "ARCHIVED":
                    archived_count += 1
                else:
                    active_count += 1

            parent_count = parent_repo.count()
            assessment_count = assessment_repo.count()
            active_students = student_repo.list_active_non_archived()

            students_without_parent = sum(
                1 for student in active_students if not parent_repo.get_by_student(student.id)
            )
            students_without_assessment = sum(
                1 for student in active_students if not assessment_repo.get_by_student(student.id)
            )

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
            summaries = [WorkspaceSummary(
                workspace_id="student", name="Student Workspace", icon="👨‍🎓",
                description="Manage students, parents, assessments", summary_text=summary_text,
                health_status=health_status, health_details=health_details,
                quick_action_label="Open →", quick_action_target="student"
            )]

            class_count = class_repo.count()
            session_count = session_repo.count_by_status("Scheduled")
            teacher_count = teacher_repo.count()
            user = get_current_user()

            if user and (user.has_permission("teacher.view") or user.is_admin):
                summaries.append(WorkspaceSummary(
                    workspace_id="teacher", name="Teacher Workspace", icon="👨‍🏫",
                    description="Teaching activities and classes",
                    summary_text=f"{teacher_count} teachers, {class_count} classes, {session_count} upcoming sessions",
                    health_status="good", health_details="", quick_action_label="Open →", quick_action_target="teacher"
                ))

            if user and (user.has_permission("class.view") or user.is_admin):
                summaries.append(WorkspaceSummary(
                    workspace_id="class", name="Class Workspace", icon="📚",
                    description="Manage classes, enrollments, schedules",
                    summary_text=f"{class_count} classes", health_status="good", health_details="",
                    quick_action_label="Open →", quick_action_target="class"
                ))

            if user and (user.has_permission("finance.view") or user.is_admin):
                from centermanager.services.outstanding_service import OutstandingService
                stats = OutstandingService(self._session_factory).get_outstanding_stats()
                revenue = stats.get("total_paid", 0)
                outstanding = stats.get("total_outstanding", 0)
                summaries.append(WorkspaceSummary(
                    workspace_id="finance", name="Finance Workspace", icon="💰",
                    description="Invoices, payments, revenue",
                    summary_text=f"Revenue: {revenue:,.0f} VND, Outstanding: {outstanding:,.0f} VND",
                    health_status="good", health_details="", quick_action_label="Open →", quick_action_target="finance"
                ))

            if user and (user.has_permission("employee.view.self") or user.has_permission("employee.view.all") or user.is_admin):
                if user.is_admin or user.has_permission("employee.view.all"):
                    employee_count = employee_repo.count_non_archived()
                    active_employee_count = employee_repo.count_by_status("ACTIVE")
                    summary_text = f"{employee_count} employees, {active_employee_count} active"
                    description = "Manage employee profiles and HR information"
                else:
                    summary_text = "My employee profile and attendance"
                    description = "View your employee profile and attendance"
                summaries.append(WorkspaceSummary(
                    workspace_id="employee", name="Employee Workspace", icon="👥",
                    description=description, summary_text=summary_text,
                    health_status="good", health_details="", quick_action_label="Open →", quick_action_target="employee"
                ))

            if user and (user.has_permission("user.manage") or user.is_admin):
                summaries.append(WorkspaceSummary(
                    workspace_id="admin", name="Admin Workspace", icon="⚙️",
                    description="User management and system settings",
                    summary_text="Manage users and configuration", health_status="good", health_details="",
                    quick_action_label="Open →", quick_action_target="admin"
                ))

            self._cache = summaries
            self._cache_invalidated = False
            logger.info(f"HomeDashboard cache updated: total={total_students}, active={active_count}, archived={archived_count}")
            return summaries

    def refresh(self) -> None:
        """Force refresh cache."""
        self._cache_invalidated = True
