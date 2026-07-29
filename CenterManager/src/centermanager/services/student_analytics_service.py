# -*- coding: utf-8 -*-
from typing import List, Tuple, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from collections import Counter

from centermanager.models.student import Student
from centermanager.models.assessment import Assessment


class StudentAnalyticsService:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def get_dashboard_analytics(self) -> Dict[str, Any]:
        with self._session_factory() as session:
            # Enrollment trend (last 6 months)
            six_months_ago = datetime.now() - timedelta(days=180)
            students = session.query(Student).filter(
                Student.created_at >= six_months_ago
            ).all()
            month_counts = Counter()
            for s in students:
                month_key = s.created_at.strftime("%Y-%m")
                month_counts[month_key] += 1
            enrollment_trend = sorted(month_counts.items())

            # Assessment distribution
            assessments = session.query(Assessment).all()
            type_counts = Counter(a.assessment_type for a in assessments if a.assessment_type)
            assessment_distribution = list(type_counts.items())

            # Age distribution
            age_counts = Counter()
            today = datetime.now().date()
            for s in session.query(Student).all():
                if s.date_of_birth:
                    age = today.year - s.date_of_birth.year - (
                        (today.month, today.day) < (s.date_of_birth.month, s.date_of_birth.day)
                    )
                    age_group = f"{age//10*10}-{age//10*10+9}"
                    age_counts[age_group] += 1
            age_distribution = list(age_counts.items())

            # Average score
            scores = [a.overall_score for a in assessments if a.overall_score is not None]
            avg_score = sum(scores) / len(scores) if scores else 0

            return {
                "enrollment_trend": enrollment_trend,
                "assessment_distribution": assessment_distribution,
                "age_distribution": age_distribution,
                "average_score": avg_score,
            }

    def get_recent_students(self, limit: int = 5) -> List[Student]:
        with self._session_factory() as session:
            return session.query(Student).order_by(
                Student.created_at.desc()
            ).limit(limit).all()