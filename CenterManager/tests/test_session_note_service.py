# -*- coding: utf-8 -*-
"""
Tests for SessionNoteService.
"""
import pytest
from datetime import date

from sqlalchemy.orm import sessionmaker

from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.class_ import Class
from centermanager.models.session import Session, SessionStatus
from centermanager.models.session_note import TeachingProgress, ClassAtmosphere
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import (
    SessionNoteService,
    SessionNoteValidationError,
    SessionNoteNotFoundError
)


@pytest.fixture
def db_session(test_db_path):
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def class_obj(db_session):
    cls = Class(name="Test Class", course="Python")
    db_session.add(cls)
    db_session.commit()
    return cls


@pytest.fixture
def session_obj(db_session, class_obj):
    sess = Session(
        class_id=class_obj.id,
        session_number=1,
        title="Session 1",
        scheduled_date=date(2026, 7, 28),
        status=SessionStatus.COMPLETED.value
    )
    db_session.add(sess)
    db_session.commit()
    return sess


@pytest.fixture
def session_service(db_session):
    # Tạo session_factory từ db_session
    engine = db_session.get_bind()
    session_factory = sessionmaker(bind=engine)
    return SessionService(session_factory)


@pytest.fixture
def note_service(db_session, session_service):
    engine = db_session.get_bind()
    session_factory = sessionmaker(bind=engine)
    return SessionNoteService(session_factory, session_service)


def test_create_note(note_service, session_obj):
    note = note_service.create_note(
        session_id=session_obj.id,
        teaching_progress=TeachingProgress.COMPLETED.value,
        class_atmosphere=ClassAtmosphere.GOOD.value,
        difficulties="Some issues",
        next_plan="Review",
        remark="Good session"
    )
    assert note.id is not None
    assert note.session_id == session_obj.id
    assert note.teaching_progress == TeachingProgress.COMPLETED.value
    assert note.class_atmosphere == ClassAtmosphere.GOOD.value


def test_create_note_duplicate(note_service, session_obj):
    note_service.create_note(
        session_id=session_obj.id,
        teaching_progress=TeachingProgress.COMPLETED.value,
        class_atmosphere=ClassAtmosphere.GOOD.value
    )
    with pytest.raises(SessionNoteValidationError, match="already exists"):
        note_service.create_note(
            session_id=session_obj.id,
            teaching_progress=TeachingProgress.COMPLETED.value,
            class_atmosphere=ClassAtmosphere.GOOD.value
        )


def test_create_note_not_completed(note_service, db_session, class_obj):
    # Tạo session chưa completed
    sess = Session(
        class_id=class_obj.id,
        session_number=2,
        title="Session 2",
        scheduled_date=date(2026, 7, 29),
        status=SessionStatus.SCHEDULED.value
    )
    db_session.add(sess)
    db_session.commit()

    with pytest.raises(SessionNoteValidationError, match="only be created for COMPLETED"):
        note_service.create_note(
            session_id=sess.id,
            teaching_progress=TeachingProgress.COMPLETED.value,
            class_atmosphere=ClassAtmosphere.GOOD.value
        )


def test_get_note(note_service, session_obj):
    created = note_service.create_note(
        session_id=session_obj.id,
        teaching_progress=TeachingProgress.COMPLETED.value,
        class_atmosphere=ClassAtmosphere.GOOD.value,
        difficulties="Some issues"
    )
    fetched = note_service.get_note(session_obj.id)
    assert fetched.id == created.id
    assert fetched.difficulties == "Some issues"


def test_update_note(note_service, session_obj):
    note_service.create_note(
        session_id=session_obj.id,
        teaching_progress=TeachingProgress.COMPLETED.value,
        class_atmosphere=ClassAtmosphere.GOOD.value,
        difficulties="Old issue"
    )
    updated = note_service.update_note(
        session_id=session_obj.id,
        difficulties="New issue",
        next_plan="Plan updated"
    )
    assert updated.difficulties == "New issue"
    assert updated.next_plan == "Plan updated"


def test_delete_note(note_service, session_obj):
    note_service.create_note(
        session_id=session_obj.id,
        teaching_progress=TeachingProgress.COMPLETED.value,
        class_atmosphere=ClassAtmosphere.GOOD.value
    )
    note_service.delete_note(session_obj.id)
    fetched = note_service.get_note(session_obj.id)
    assert fetched is None


def test_delete_note_not_found(note_service, session_obj):
    with pytest.raises(SessionNoteNotFoundError):
        note_service.delete_note(session_obj.id)


def test_invalid_teaching_progress(note_service, session_obj):
    with pytest.raises(SessionNoteValidationError):
        note_service.create_note(
            session_id=session_obj.id,
            teaching_progress="INVALID",
            class_atmosphere=ClassAtmosphere.GOOD.value
        )


def test_invalid_class_atmosphere(note_service, session_obj):
    with pytest.raises(SessionNoteValidationError):
        note_service.create_note(
            session_id=session_obj.id,
            teaching_progress=TeachingProgress.COMPLETED.value,
            class_atmosphere="INVALID"
        )