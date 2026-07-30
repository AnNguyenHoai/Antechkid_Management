# -*- coding: utf-8 -*-
"""
HomeDashboardService - provides aggregated data for Home Workspace (Workspace Launcher).
Now simplified: only provides workspace summaries for the launcher.
"""
import logging
from dataclasses import dataclass
from typing import List

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

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceSummary:
    workspace_id: str
    name: str
    icon: str
    description: str
    summary_text: str
    health_status: str          # "good", "warning", "critical"
    health_details: str
    quick_action_label: str
    quick_action_target: str


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

            # Finance placeholder (always visible but no data yet)
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