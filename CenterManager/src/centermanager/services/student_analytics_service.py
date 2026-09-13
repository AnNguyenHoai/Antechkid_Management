# -*- coding: utf-8 -*-
"""Student analytics application service.

The service owns analytics calculations; all database access is delegated to
repositories supplied by RepositoryProvider.
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter

from sqlalchemy.orm import sessionmaker

from centermanager.models.student import Student
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider


class StudentAnalyticsService:
    def __init__(self, session_factory: sessionmaker, repository_provider: RepositoryProvider | None = None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

    def get_dashboard_analytics(self) -> Dict[str, Any]:
        with self._session_factory() as session:
            student_repo = self._repository_provider.students(session)
            assessment_repo = self._repository_provider.assessments(session)
            students = student_repo.list_active()
            assessments = assessment_repo.list_all()

            # Student Workspace population rule: exclude soft-deleted students.
            total_students = len(students)

            # Enrollment trend (last 6 months)
            six_months_ago = datetime.now() - timedelta(days=180)
            recent_students = [s for s in students if s.created_at >= six_months_ago]
            month_counts = Counter()
            for s in recent_students:
                month_key = s.created_at.strftime("%Y-%m")
                month_counts[month_key] += 1
            enrollment_trend = sorted(month_counts.items())

            # Assessment distribution
            type_counts = Counter(a.assessment_type for a in assessments if a.assessment_type)
            assessment_distribution = list(type_counts.items())

            # Age distribution
            age_counts = Counter()
            today = datetime.now().date()
            for s in students:
                if s.date_of_birth:
                    age = today.year - s.date_of_birth.year - (
                        (today.month, today.day) < (s.date_of_birth.month, s.date_of_birth.day)
                    )
                    age_group = f"{age//10*10}-{age//10*10+9}"
                    age_counts[age_group] += 1
            age_distribution = list(age_counts.items())

            # Score distribution
            score_counts = Counter()
            scores = []
            for a in assessments:
                if a.overall_score is not None:
                    scores.append(a.overall_score)
                    score_counts[a.overall_score] += 1
            score_distribution = sorted(score_counts.items())

            # Average score
            avg_score = sum(scores) / len(scores) if scores else 0

            # Monthly growth
            last_month = datetime.now().replace(day=1) - timedelta(days=1)
            two_months_ago = last_month.replace(day=1) - timedelta(days=1)
            last_month_start = last_month.replace(day=1)
            two_months_ago_start = two_months_ago.replace(day=1)

            last_month_count = sum(
                1 for s in students
                if last_month_start <= s.created_at < last_month_start + timedelta(days=32)
            )
            two_months_ago_count = sum(
                1 for s in students
                if two_months_ago_start <= s.created_at < two_months_ago_start + timedelta(days=32)
            )

            if two_months_ago_count > 0:
                growth = ((last_month_count - two_months_ago_count) / two_months_ago_count) * 100
            else:
                growth = 0

            return {
                "total_students": total_students,
                "enrollment_trend": enrollment_trend,
                "assessment_distribution": assessment_distribution,
                "age_distribution": age_distribution,
                "score_distribution": score_distribution,
                "average_score": avg_score,
                "monthly_growth": growth,
            }

    def get_recent_students(self, limit: int = 5) -> List[Student]:
        with self._session_factory() as session:
            repo = self._repository_provider.students(session)
            students = repo.list_active()
            return sorted(students, key=lambda s: s.created_at, reverse=True)[:limit]
