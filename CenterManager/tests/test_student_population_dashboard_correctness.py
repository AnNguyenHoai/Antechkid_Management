# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta

from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models.student import Student
from centermanager.models.parent import Parent
from centermanager.services.student_dashboard_service import StudentDashboardService
from centermanager.services.student_analytics_service import StudentAnalyticsService


def _services(test_db_path):
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return factory, StudentDashboardService(factory), StudentAnalyticsService(factory)


def test_dashboard_population_excludes_soft_deleted_but_keeps_archived(test_db_path):
    factory, dashboard, _ = _services(test_db_path)
    with factory() as session:
        active = Student(student_code="HS001", full_name="Active", status="ACTIVE")
        archived = Student(student_code="HS002", full_name="Archived", status="ARCHIVED")
        deleted = Student(
            student_code="HS003",
            full_name="Deleted",
            status="ACTIVE",
            deleted_at=datetime.now(),
        )
        session.add_all([active, archived, deleted])
        session.commit()

    stats = dashboard.get_stats()

    assert stats.total == 2
    assert stats.active == 1
    assert stats.archived == 1
    assert stats.total == stats.active + stats.archived


def test_parent_coverage_is_not_assessment_completion_rate(test_db_path):
    factory, dashboard, _ = _services(test_db_path)
    with factory() as session:
        with_parent = Student(student_code="HS001", full_name="Has Parent")
        without_parent = Student(student_code="HS002", full_name="No Parent")
        session.add_all([with_parent, without_parent])
        session.flush()
        session.add(Parent(student_id=with_parent.id, name="Parent", phone="123"))
        session.commit()

    insights = dashboard.get_quick_insights()

    assert insights.total_parents == 1
    assert insights.parent_coverage_rate == 50.0
    assert insights.assessment_completion_rate == 0.0


def test_analytics_uses_same_non_deleted_population(test_db_path):
    factory, dashboard, analytics = _services(test_db_path)
    with factory() as session:
        session.add_all([
            Student(student_code="HS001", full_name="Active", status="ACTIVE"),
            Student(student_code="HS002", full_name="Archived", status="ARCHIVED"),
            Student(
                student_code="HS003",
                full_name="Deleted",
                status="ACTIVE",
                deleted_at=datetime.now(),
            ),
        ])
        session.commit()

    assert dashboard.get_stats().total == 2
    assert analytics.get_dashboard_analytics()["total_students"] == 2


def test_recent_students_excludes_soft_deleted(test_db_path):
    factory, _, analytics = _services(test_db_path)
    with factory() as session:
        visible = Student(student_code="HS001", full_name="Visible")
        deleted = Student(
            student_code="HS002",
            full_name="Deleted",
            deleted_at=datetime.now(),
        )
        session.add_all([visible, deleted])
        session.commit()

    recent = analytics.get_recent_students(limit=10)

    assert [student.full_name for student in recent] == ["Visible"]
