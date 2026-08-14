# tests/test_transaction_cancel.py
# -*- coding: utf-8 -*-
"""Tests for transaction cancel with domain mutations."""

import pytest
from datetime import date
from pathlib import Path

from centermanager.core.paths import get_paths
from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.events.event_bus import EventBus
from centermanager.events.student_events import StudentArchived, StudentActivated
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def temp_runtime_with_db(temp_runtime):
    """Create temp runtime with database and student."""
    paths = get_paths()
    db_path = paths.database_dir / "center.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        student = Student(student_code="HS001", full_name="Test Student", status="ACTIVE")
        session.add(student)
        session.commit()
    return paths


@pytest.fixture
def student_service(temp_runtime_with_db):
    """Return StudentService and its EventBus."""
    session_factory = sessionmaker(bind=create_engine_for_path(get_paths().database_dir / "center.db"))
    timeline_service = MockTimelineService(session_factory)
    event_bus = EventBus()
    service = StudentService(session_factory, timeline_service, event_bus=event_bus)
    return service, event_bus


class MockTimelineService:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def log_event(self, *args, **kwargs):
        pass


class MockCollaborationManager:
    def __init__(self):
        self._writing = True

    def is_writing(self):
        return self._writing

    def release_write(self):
        self._writing = False

    def ensure_write(self):
        return self._writing

    def request_write(self):
        return True


def test_archive_then_cancel_rollback(temp_runtime_with_db, student_service):
    """Archive then Cancel should restore ACTIVE status."""
    service, event_bus = student_service

    # Get student
    students = service.list_students()
    assert len(students) == 1
    student = students[0]
    assert student.status == "ACTIVE"

    # Setup transaction
    cm_mock = MockCollaborationManager()
    tx = WriteTransactionManager(cm_mock)

    # Register event listener on the same event bus used by service
    def on_archived(event):
        if tx.is_editing:
            tx.mark_dirty()
            print(f"Marked dirty for student {event.student_id}")

    event_bus.register(StudentArchived, on_archived)

    # Start editing
    def save_local():
        return True

    tx.start_editing(save_local)
    assert tx.is_editing is True
    assert tx.has_changes() is False

    # Archive student (will publish event)
    service.archive_student(student.id)

    # Event should mark dirty
    assert tx.has_changes() is True

    # Cancel editing with force=True
    tx.cancel_editing(force=True)

    # Reload student from fresh session
    Session = sessionmaker(bind=create_engine_for_path(get_paths().database_dir / "center.db"))
    with Session() as sess:
        s = sess.get(Student, student.id)
        assert s.status == "ACTIVE"  # restored
    assert tx.state == WriteTransactionState.IDLE
    assert not cm_mock.is_writing()