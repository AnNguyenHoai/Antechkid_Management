"""Regression: class archive events must not crash Student Workspace dashboard."""
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

from centermanager.services.student_dashboard_service import StudentDashboardService


def test_recent_activities_class_timeline():
    event = SimpleNamespace(
        title="Class archived",
        created_at=datetime(2026, 10, 28, 22, 0),
        class_=SimpleNamespace(name="Python L1"),
    )

    class Provider:
        def class_timeline(self, session):
            return SimpleNamespace(list_all=lambda: [event])

    @contextmanager
    def session_factory():
        yield object()

    activities = StudentDashboardService(session_factory, Provider()).get_recent_activities()
    assert len(activities) == 1
    assert activities[0].student_name == "Python L1"
    assert activities[0].student_code == ""
    assert activities[0].title == "Class archived"
