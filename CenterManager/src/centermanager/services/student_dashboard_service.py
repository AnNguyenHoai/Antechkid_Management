# -*- coding: utf-8 -*-
"""
StudentDashboardService - provides aggregated data for the Student Workspace dashboard.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.student import Student
from centermanager.models.timeline_event import TimelineEvent
from centermanager.models.assessment import Assessment
from centermanager.models.parent import Parent
from centermanager.repositories.student_repository import StudentRepository
from centermanager.repositories.timeline_repository import TimelineRepository
from centermanager.repositories.assessment_repository import AssessmentRepository
from centermanager.repositories.parent_repository import ParentRepository

logger = logging.getLogger(__name__)


@dataclass
class DashboardStats:
    total: int
    active: int
    archived: int
    new_this_month: int


@dataclass
class RecentActivity:
    student_name: str
    student_code: str
    title: str
    time: datetime


@dataclass
class AttentionStudent:
    student_id: int
    student_code: str
    full_name: str
    reason: str


class StudentDashboardService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get_stats(self) -> DashboardStats:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            all_students = repo.list_all_including_deleted()
            total = len(all_students)
            active = sum(1 for s in all_students if s.deleted_at is None)
            archived = total - active
            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_this_month = sum(1 for s in all_students
                                if s.created_at >= month_start and s.deleted_at is None)
            logger.info(f"Dashboard stats: total={total}, active={active}, archived={archived}, new={new_this_month}")
            return DashboardStats(...)

    def get_recent_activities(self, limit: int = 10) -> List[RecentActivity]:
        with self._session_factory() as session:
            events = session.query(TimelineEvent).order_by(
                TimelineEvent.created_at.desc()
            ).limit(limit).all()
            result = []
            for ev in events:
                student = ev.student
                result.append(RecentActivity(
                    student_name=student.full_name,
                    student_code=student.student_code,
                    title=ev.title,
                    time=ev.created_at
                ))
            return result

    def get_students_requiring_attention(self) -> List[AttentionStudent]:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            active_students = repo.list_active()
            parent_repo = ParentRepository(session)
            assessment_repo = AssessmentRepository(session)
            result = []
            for student in active_students:
                parents = parent_repo.get_by_student(student.id)
                if not parents:
                    result.append(AttentionStudent(
                        student_id=student.id,
                        student_code=student.student_code,
                        full_name=student.full_name,
                        reason="Missing parent information"
                    ))
                    continue
                assessments = assessment_repo.get_by_student(student.id)
                if not assessments:
                    result.append(AttentionStudent(
                        student_id=student.id,
                        student_code=student.student_code,
                        full_name=student.full_name,
                        reason="No assessment recorded"
                    ))
                    continue
            return result