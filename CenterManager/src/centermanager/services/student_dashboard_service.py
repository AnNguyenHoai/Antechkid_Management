# -*- coding: utf-8 -*-
"""StudentDashboardService - aggregated data for the Student Workspace dashboard.

The service owns presentation aggregation only. Database access is delegated to
repositories supplied by RepositoryProvider.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List

from sqlalchemy.orm import sessionmaker

from centermanager.models.student import Student
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider

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


@dataclass
class UpcomingEvent:
    event_type: str
    student_name: str
    student_code: str
    date: date
    details: str


@dataclass
class QuickInsights:
    avg_assessment_score: float
    avg_age: float
    total_parents: int
    assessment_completion_rate: float
    parent_coverage_rate: float


@dataclass
class TodaySummary:
    today_classes: int = 0
    today_assessments: int = 0
    today_birthdays: list = None
    upcoming_sessions: int = 0
    pending_tasks: int = 0


class StudentDashboardService:
    def __init__(self, session_factory: sessionmaker, repository_provider: RepositoryProvider | None = None) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

    def get_stats(self) -> DashboardStats:
        """Get dashboard statistics with correct active/archived counts based on status."""
        with self._session_factory() as session:
            repo = self._repository_provider.students(session)
            all_students = repo.list_all_including_deleted()
            visible_students = [s for s in all_students if s.deleted_at is None]
            total = len(visible_students)

            active = sum(1 for s in visible_students if s.status != "ARCHIVED")
            archived = sum(1 for s in visible_students if s.status == "ARCHIVED")

            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_this_month = sum(
                1 for s in visible_students
                if s.created_at >= month_start and s.status != "ARCHIVED"
            )
            logger.info(f"Dashboard stats: total={total}, active={active}, archived={archived}, new={new_this_month}")
            return DashboardStats(
                total=total,
                active=active,
                archived=archived,
                new_this_month=new_this_month
            )

    def get_recent_activities(self, limit: int = 10) -> List[RecentActivity]:
        with self._session_factory() as session:
            repo = self._repository_provider.class_timeline(session)
            events = sorted(repo.list_all(), key=lambda ev: ev.created_at, reverse=True)[:limit]
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

    def get_students_requiring_attention(self, limit: int = 10) -> List[AttentionStudent]:
        with self._session_factory() as session:
            student_repo = self._repository_provider.students(session)
            parent_repo = self._repository_provider.parents(session)
            assessment_repo = self._repository_provider.assessments(session)
            active_students = student_repo.list_active_non_archived()
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
            return result[:limit]

    def get_upcoming_events(self) -> List[UpcomingEvent]:
        today = date.today()
        upcoming = []
        with self._session_factory() as session:
            student_repo = self._repository_provider.students(session)
            session_repo = self._repository_provider.sessions(session)
            students = student_repo.list_active_non_archived()
            for s in students:
                if s.date_of_birth:
                    dob = s.date_of_birth
                    next_birthday = date(today.year, dob.month, dob.day)
                    if next_birthday < today:
                        next_birthday = date(today.year + 1, dob.month, dob.day)
                    days_until = (next_birthday - today).days
                    if 0 <= days_until <= 30:
                        upcoming.append(UpcomingEvent(
                            event_type="birthday",
                            student_name=s.full_name,
                            student_code=s.student_code,
                            date=next_birthday,
                            details=f"Birthday in {days_until} days"
                        ))

            sessions = session_repo.list_all()
            week_later = today + timedelta(days=7)
            for sess in sessions:
                if today <= sess.scheduled_date <= week_later and sess.status == "Scheduled":
                    class_name = sess.class_.name if sess.class_ else "Class"
                    upcoming.append(UpcomingEvent(
                        event_type="session",
                        student_name="",
                        student_code="",
                        date=sess.scheduled_date,
                        details=f"Session: {sess.title} ({class_name})"
                    ))
            upcoming.sort(key=lambda x: x.date)
            return upcoming[:10]

    def get_quick_insights(self) -> QuickInsights:
        with self._session_factory() as session:
            student_repo = self._repository_provider.students(session)
            assessment_repo = self._repository_provider.assessments(session)
            parent_repo = self._repository_provider.parents(session)
            active_students = student_repo.list_active_non_archived()
            total_students = len(active_students)
            total_age = 0
            age_count = 0
            today = date.today()
            for s in active_students:
                if s.date_of_birth:
                    age = today.year - s.date_of_birth.year - ((today.month, today.day) < (s.date_of_birth.month, s.date_of_birth.day))
                    total_age += age
                    age_count += 1
            avg_age = total_age / age_count if age_count > 0 else 0

            all_assessments = assessment_repo.list_all()
            scores = [a.overall_score for a in all_assessments if a.overall_score is not None]
            avg_score = sum(scores) / len(scores) if scores else 0

            active_student_ids = {s.id for s in active_students}
            students_with_parent = {
                p.student_id for p in parent_repo.list_all()
                if p.student_id in active_student_ids
            }
            parent_count = len(students_with_parent)
            parent_coverage_rate = len(students_with_parent) / total_students if total_students > 0 else 0

            students_with_assessment = {
                a.student_id for a in all_assessments
                if a.student_id in active_student_ids
            }
            completion_rate = len(students_with_assessment) / total_students if total_students > 0 else 0

            return QuickInsights(
                avg_assessment_score=round(avg_score, 1),
                avg_age=round(avg_age, 1),
                total_parents=parent_count,
                assessment_completion_rate=round(completion_rate * 100, 1),
                parent_coverage_rate=round(parent_coverage_rate * 100, 1)
            )

    def get_today_summary(self) -> TodaySummary:
        today = date.today()
        with self._session_factory() as session:
            student_repo = self._repository_provider.students(session)
            session_repo = self._repository_provider.sessions(session)
            assessment_repo = self._repository_provider.assessments(session)
            parent_repo = self._repository_provider.parents(session)

            sessions = session_repo.list_all()
            sessions_today = sum(1 for s in sessions if s.scheduled_date == today and s.status == 'Scheduled')
            upcoming = sum(1 for s in sessions if today < s.scheduled_date <= today + timedelta(days=7) and s.status == 'Scheduled')
            all_assessments = assessment_repo.list_all()
            assessments_today = sum(1 for a in all_assessments if a.assessment_date == today)

            students = student_repo.list_active_non_archived()
            today_birthdays = [
                s.full_name for s in students
                if s.date_of_birth and s.date_of_birth.month == today.month and s.date_of_birth.day == today.day
            ]

            active_student_ids = {s.id for s in students}
            students_with_parent = {
                p.student_id for p in parent_repo.list_all()
                if p.student_id in active_student_ids
            }
            students_with_assessment = {
                a.student_id for a in all_assessments
                if a.student_id in active_student_ids
            }
            students_without_parent = len(active_student_ids - students_with_parent)
            students_without_assessment = len(active_student_ids - students_with_assessment)
            pending_tasks = students_without_parent + students_without_assessment

            return TodaySummary(
                today_classes=sessions_today,
                today_assessments=assessments_today,
                today_birthdays=today_birthdays,
                upcoming_sessions=upcoming,
                pending_tasks=pending_tasks
            )
