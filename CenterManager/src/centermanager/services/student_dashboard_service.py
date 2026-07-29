# -*- coding: utf-8 -*-
"""
StudentDashboardService - provides aggregated data for the Student Workspace dashboard.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import sessionmaker
from datetime import date, timedelta
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
@dataclass
class UpcomingEvent:
    event_type: str  # "birthday", "assessment", "session"
    student_name: str
    student_code: str
    date: date
    details: str

@dataclass
class QuickInsights:
    avg_assessment_score: float
    avg_age: float
    total_parents: int
    assessment_completion_rate: float  # percentage of students with at least one assessment

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
            # Sửa lỗi: trả về đúng tham số
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
    def get_students_requiring_attention(self, limit: int = 10) -> List[AttentionStudent]:
        """Get students needing attention."""
        with self._session_factory() as session:
            repo = StudentRepository(session)
            parent_repo = ParentRepository(session)
            assessment_repo = AssessmentRepository(session)
            active_students = repo.list_active()
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
        """Get upcoming events (birthdays, assessments, sessions)."""
        today = date.today()
        upcoming = []
        with self._session_factory() as session:
            # Upcoming birthdays (next 30 days)
            students = session.query(Student).all()
            for s in students:
                if s.date_of_birth:
                    # Calculate next birthday
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
            # Upcoming assessments (next 7 days) - if we have assessment_date, else we can use created_at
            # For now, we'll just list recent assessments? Actually we don't have future assessments.
            # We can skip or use a placeholder.
            # Upcoming sessions (next 7 days)
            week_later = today + timedelta(days=7)
            sessions = session.query(Session).filter(
                Session.scheduled_date >= today,
                Session.scheduled_date <= week_later,
                Session.status == "Scheduled"
            ).all()
            for sess in sessions:
                # Get class name if needed
                class_name = sess.class_.name if sess.class_ else "Class"
                upcoming.append(UpcomingEvent(
                    event_type="session",
                    student_name="",  # session doesn't have direct student, we can show class name
                    student_code="",
                    date=sess.scheduled_date,
                    details=f"Session: {sess.title} ({class_name})"
                ))
            # Sort by date
            upcoming.sort(key=lambda x: x.date)
            return upcoming[:10]

    def get_quick_insights(self) -> QuickInsights:
        """Calculate quick insights."""
        with self._session_factory() as session:
            repo = StudentRepository(session)
            active_students = repo.list_active()
            total_students = len(active_students)
            # Average age
            total_age = 0
            age_count = 0
            today = date.today()
            for s in active_students:
                if s.date_of_birth:
                    age = today.year - s.date_of_birth.year - ((today.month, today.day) < (s.date_of_birth.month, s.date_of_birth.day))
                    total_age += age
                    age_count += 1
            avg_age = total_age / age_count if age_count > 0 else 0

            # Average assessment score
            assessment_repo = AssessmentRepository(session)
            all_assessments = session.query(Assessment).all()
            scores = [a.overall_score for a in all_assessments if a.overall_score is not None]
            avg_score = sum(scores) / len(scores) if scores else 0

            # Total parents
            parent_count = session.query(Parent).count()

            # Assessment completion rate (students with at least one assessment)
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