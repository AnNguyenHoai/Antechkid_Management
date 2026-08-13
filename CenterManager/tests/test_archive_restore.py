# -*- coding: utf-8 -*-
"""Tests for archive/restore and dashboard stats."""

import pytest
from datetime import date

from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.services.student_dashboard_service import StudentDashboardService
from centermanager.events.event_bus import EventBus
from centermanager.events.student_events import StudentArchived, StudentActivated  # <-- THÊM DÒNG NÀY
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session(test_db_path):
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_archive_dashboard_stats(db_session):
    """Test that archiving updates dashboard stats correctly."""
    session_factory = lambda: db_session
    event_bus = EventBus()
    student_service = StudentService(session_factory, event_bus=event_bus)
    dashboard_service = StudentDashboardService(session_factory)

    # Create 10 students
    for i in range(1, 11):
        student_service.create_student(full_name=f"Student {i}")

    # Check initial stats
    stats = dashboard_service.get_stats()
    assert stats.total == 10
    assert stats.active == 10
    assert stats.archived == 0

    # Archive one student
    student = student_service.list_students()[0]
    student_service.archive_student(student.id)

    # Check stats
    stats = dashboard_service.get_stats()
    assert stats.total == 10
    assert stats.active == 9
    assert stats.archived == 1

    # Activate it back
    student_service.activate_student(student.id)

    stats = dashboard_service.get_stats()
    assert stats.total == 10
    assert stats.active == 10
    assert stats.archived == 0


def test_archive_event(db_session):
    """Test that archive publishes StudentArchived event."""
    event_bus = EventBus()
    session_factory = lambda: db_session
    student_service = StudentService(session_factory, event_bus=event_bus)

    student = student_service.create_student(full_name="Test")
    events_collected = []

    def listener(event):
        events_collected.append(event)

    event_bus.register(StudentArchived, listener)

    student_service.archive_student(student.id)

    assert len(events_collected) == 1
    event = events_collected[0]
    assert isinstance(event, StudentArchived)
    assert event.student_id == student.id
    assert event.student_code == student.student_code


def test_activate_event(db_session):
    """Test that activate publishes StudentActivated event."""
    event_bus = EventBus()
    session_factory = lambda: db_session
    student_service = StudentService(session_factory, event_bus=event_bus)

    student = student_service.create_student(full_name="Test")
    # Archive first
    student_service.archive_student(student.id)
    events_collected = []

    def listener(event):
        events_collected.append(event)

    event_bus.register(StudentActivated, listener)

    student_service.activate_student(student.id)

    assert len(events_collected) == 1
    event = events_collected[0]
    assert isinstance(event, StudentActivated)
    assert event.student_id == student.id