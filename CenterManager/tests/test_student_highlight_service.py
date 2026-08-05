# -*- coding: utf-8 -*-
"""
Tests for StudentHighlightService.
"""
import pytest
from datetime import date

from sqlalchemy.orm import sessionmaker

from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.class_ import Class
from centermanager.models.session import Session, SessionStatus
from centermanager.models.student import Student
from centermanager.models.enrollment import Enrollment
from centermanager.models.student_highlight import HighlightType
from centermanager.services.session_service import SessionService
from centermanager.services.student_service import StudentService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.events.event_bus import EventBus
from centermanager.events.highlight_events import StudentHighlightCreated
from centermanager.events.handlers.highlight_timeline_handler import HighlightTimelineHandler
from centermanager.services.timeline_service import TimelineService
from centermanager.services.parent_service import ParentService  # just for dependencies
from centermanager.core.current_user import CurrentUserContext
from centermanager.models.user import User
from centermanager.models.role import Role
from centermanager.models.permission import Permission


@pytest.fixture
def db_session(test_db_path):
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def admin_user(db_session):
    """Create an admin user with full permissions."""
    role = db_session.query(Role).filter(Role.name == "admin").first()
    if not role:
        role = Role(name="admin", display_name="Administrator", is_system=True)
        db_session.add(role)
        db_session.commit()
        # Thêm permissions
        for perm_name in ["lesson.view", "lesson.create", "lesson.update", "lesson.cancel"]:
            perm = db_session.query(Permission).filter(Permission.name == perm_name).first()
            if not perm:
                perm = Permission(name=perm_name, description=perm_name)
                db_session.add(perm)
                db_session.commit()
            if perm not in role.permissions:
                role.permissions.append(perm)
        db_session.commit()

    user = User(
        username="admin_test",
        password_hash="dummy",
        full_name="Admin Test",
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def class_obj(db_session):
    cls = Class(name="Test Class", course="Python")
    db_session.add(cls)
    db_session.commit()
    return cls


@pytest.fixture
def student_obj(db_session):
    s = Student(student_code="HS001", full_name="Test Student")
    db_session.add(s)
    db_session.commit()
    return s


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
def enrollment(db_session, student_obj, class_obj):
    enr = Enrollment(
        student_id=student_obj.id,
        class_id=class_obj.id,
        class_name=class_obj.name,
        course_name=class_obj.course,
    )
    db_session.add(enr)
    db_session.commit()
    return enr


@pytest.fixture
def services(db_session, admin_user, class_obj, student_obj, session_obj, enrollment):
    engine = db_session.get_bind()
    session_factory = sessionmaker(bind=engine)

    timeline_service = TimelineService(session_factory)
    student_service = StudentService(session_factory, timeline_service)
    session_service = SessionService(session_factory)
    event_bus = EventBus()
    highlight_service = StudentHighlightService(session_factory, session_service, event_bus)

    # Register handler
    handler = HighlightTimelineHandler(timeline_service, session_service)
    event_bus.register(StudentHighlightCreated, handler)

    return {
        "highlight_service": highlight_service,
        "student_service": student_service,
        "session_service": session_service,
        "timeline_service": timeline_service,
        "event_bus": event_bus,
        "db_session": db_session,
        "admin_user": admin_user,
    }


def test_create_highlight(services, session_obj, student_obj):
    hs = services["highlight_service"]
    admin = services["admin_user"]
    with CurrentUserContext(admin):
        highlight = hs.create_highlight(
            session_id=session_obj.id,
            student_id=student_obj.id,
            highlight_type=HighlightType.POSITIVE.value,
            title="Great work",
            description="Student solved all problems",
        )
    assert highlight.id is not None
    assert highlight.session_id == session_obj.id
    assert highlight.student_id == student_obj.id
    assert highlight.type == HighlightType.POSITIVE.value


def test_create_highlight_student_not_in_class(services, session_obj, db_session):
    # Create another student not enrolled
    s2 = Student(student_code="HS002", full_name="Other")
    db_session.add(s2)
    db_session.commit()

    hs = services["highlight_service"]
    admin = services["admin_user"]
    with CurrentUserContext(admin):
        with pytest.raises(ValueError, match="not enrolled"):
            hs.create_highlight(
                session_id=session_obj.id,
                student_id=s2.id,
                highlight_type=HighlightType.POSITIVE.value,
                title="Invalid"
            )


def test_create_highlight_session_not_completed(services, class_obj):
    # Create session with SCHEDULED status
    sess = Session(
        class_id=class_obj.id,
        session_number=2,
        title="Session 2",
        scheduled_date=date(2026, 7, 29),
        status=SessionStatus.SCHEDULED.value
    )
    services["db_session"].add(sess)
    services["db_session"].commit()

    hs = services["highlight_service"]
    admin = services["admin_user"]
    with CurrentUserContext(admin):
        with pytest.raises(ValueError, match="must be COMPLETED"):
            hs.create_highlight(
                session_id=sess.id,
                student_id=1,  # invalid
                highlight_type=HighlightType.POSITIVE.value,
                title="Invalid"
            )


def test_timeline_created(services, session_obj, student_obj):
    hs = services["highlight_service"]
    timeline_service = services["timeline_service"]
    admin = services["admin_user"]

    with CurrentUserContext(admin):
        hs.create_highlight(
            session_id=session_obj.id,
            student_id=student_obj.id,
            highlight_type=HighlightType.POSITIVE.value,
            title="Great work",
            description="Excellent"
        )

    # Check timeline
    events = timeline_service.get_student_timeline(student_obj.id)
    assert len(events) >= 1
    # The latest event should be the highlight
    latest = events[0]
    assert latest.title == "Student Highlight"
    assert "Great work" in latest.description


def test_update_highlight(services, session_obj, student_obj):
    hs = services["highlight_service"]
    admin = services["admin_user"]
    with CurrentUserContext(admin):
        created = hs.create_highlight(
            session_id=session_obj.id,
            student_id=student_obj.id,
            highlight_type=HighlightType.POSITIVE.value,
            title="Old title",
            description="Old desc"
        )
        updated = hs.update_highlight(
            highlight_id=created.id,
            highlight_type=HighlightType.SUPPORT.value,
            title="New title",
            description="New desc"
        )
    assert updated.type == HighlightType.SUPPORT.value
    assert updated.title == "New title"
    assert updated.description == "New desc"


def test_delete_highlight(services, session_obj, student_obj):
    hs = services["highlight_service"]
    admin = services["admin_user"]
    with CurrentUserContext(admin):
        created = hs.create_highlight(
            session_id=session_obj.id,
            student_id=student_obj.id,
            highlight_type=HighlightType.POSITIVE.value,
            title="To delete"
        )
        hs.delete_highlight(created.id)
        # Kiểm tra danh sách rỗng
        highlights = hs.get_highlights_for_session(session_obj.id)
    assert len(highlights) == 0
    # Kiểm tra xóa lại sẽ raise lỗi
    with CurrentUserContext(admin):
        with pytest.raises(ValueError, match="not found"):
            hs.delete_highlight(created.id)