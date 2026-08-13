# -*- coding: utf-8 -*-
"""StudentDashboardService - provides aggregated data for Student Workspace dashboard."""
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.student import Student
from centermanager.models.timeline_event import TimelineEvent
from centermanager.models.assessment import Assessment
from centermanager.models.parent import Parent
from centermanager.models.session import Session
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


@dataclass
class TodaySummary:
    today_classes: int = 0
    today_assessments: int = 0
    today_birthdays: list = None
    upcoming_sessions: int = 0
    pending_tasks: int = 0


class StudentDashboardService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get_stats(self) -> DashboardStats:
        """Get dashboard statistics with correct active/archived counts based on status."""
        with self._session_factory() as session:
            repo = StudentRepository(session)
            all_students = repo.list_all_including_deleted()
            total = len(all_students)
            
            # Active: deleted_at is None AND status != 'ARCHIVED'
            # Archived: deleted_at is None AND status == 'ARCHIVED'
            active = 0
            archived = 0
            for s in all_students:
                if s.deleted_at is not None:
                    continue  # soft-deleted, not counted in active/archived
                if s.status == "ARCHIVED":
                    archived += 1
                else:
                    active += 1

            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_this_month = sum(
                1 for s in all_students
                if s.created_at >= month_start and s.deleted_at is None and s.status != "ARCHIVED"
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

    def get_students_requiring_attention(self, limit: int = 10) -> List[AttentionStudent]:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            active_students = repo.list_active()  # list_active trả về deleted_at IS NULL
            parent_repo = ParentRepository(session)
            assessment_repo = AssessmentRepository(session)
            result = []
            for student in active_students:
                # Bỏ qua archived (dù list_active đã lọc deleted_at, nhưng nếu archive đã set deleted_at thì ok)
                # Nhưng archive không set deleted_at, nên cần kiểm tra status
                if student.status == "ARCHIVED":
                    continue
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
            # Upcoming birthdays (next 30 days)
            students = session.query(Student).filter(Student.deleted_at.is_(None), Student.status != "ARCHIVED").all()
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
            # Upcoming sessions (next 7 days)
            week_later = today + timedelta(days=7)
            sessions = session.query(Session).filter(
                Session.scheduled_date >= today,
                Session.scheduled_date <= week_later,
                Session.status == "Scheduled"
            ).all()
            for sess in sessions:
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
            repo = StudentRepository(session)
            # Lấy tất cả student chưa soft delete và chưa archived
            active_students = session.query(Student).filter(
                Student.deleted_at.is_(None),
                Student.status != "ARCHIVED"
            ).all()
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

            assessment_repo = AssessmentRepository(session)
            all_assessments = session.query(Assessment).all()
            scores = [a.overall_score for a in all_assessments if a.overall_score is not None]
            avg_score = sum(scores) / len(scores) if scores else 0

            parent_count = session.query(Parent).count()

            students_with_assessment = set()
            for a in all_assessments:
                students_with_assessment.add(a.student_id)
            completion_rate = len(students_with_assessment) / total_students if total_students > 0 else 0

            return QuickInsights(
                avg_assessment_score=round(avg_score, 1),
                avg_age=round(avg_age, 1),
                total_parents=parent_count,
                assessment_completion_rate=round(completion_rate * 100, 1)
            )

    def get_today_summary(self) -> TodaySummary:
        today = date.today()
        with self._session_factory() as session:
            sessions_today = session.query(Session).filter(
                Session.scheduled_date == today,
                Session.status == 'Scheduled'
            ).count()

            assessments_today = session.query(Assessment).filter(
                Assessment.assessment_date == today
            ).count()

            students = session.query(Student).filter(Student.deleted_at.is_(None), Student.status != "ARCHIVED").all()
            today_birthdays = [
                s.full_name for s in students
                if s.date_of_birth and s.date_of_birth.month == today.month and s.date_of_birth.day == today.day
            ]

            upcoming = session.query(Session).filter(
                Session.scheduled_date > today,
                Session.scheduled_date <= today + timedelta(days=7),
                Session.status == 'Scheduled'
            ).count()

            students_without_parent = session.query(Student).filter(
                Student.deleted_at.is_(None),
                Student.status != "ARCHIVED",
                ~Student.id.in_(session.query(Parent.student_id).distinct())
            ).count()
            students_without_assessment = session.query(Student).filter(
                Student.deleted_at.is_(None),
                Student.status != "ARCHIVED",
                ~Student.id.in_(session.query(Assessment.student_id).distinct())
            ).count()
            pending_tasks = students_without_parent + students_without_assessment

            return TodaySummary(
                today_classes=sessions_today,
                today_assessments=assessments_today,
                today_birthdays=today_birthdays,
                upcoming_sessions=upcoming,
                pending_tasks=pending_tasks
            )