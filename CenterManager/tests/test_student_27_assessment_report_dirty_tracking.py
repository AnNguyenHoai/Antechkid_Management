import ast
from datetime import date
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager.events.event_bus import EventBus
from centermanager.events.student_events import StudentAssessmentChanged
from centermanager.services.assessment_service import AssessmentService


def _has_main_window_event_registration(
    source: str,
    event_name: str,
    handler_name: str,
) -> bool:
    """Match the semantic EventBus registration, independent of formatting."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) < 2:
            continue

        func = node.func
        event_arg, handler_arg = node.args[:2]
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "register"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "_event_bus"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
        ):
            continue

        if (
            isinstance(event_arg, ast.Name)
            and event_arg.id == event_name
            and isinstance(handler_arg, ast.Attribute)
            and handler_arg.attr == handler_name
            and isinstance(handler_arg.value, ast.Name)
            and handler_arg.value.id == "self"
        ):
            return True
    return False


def test_assessment_service_publishes_committed_student_assessment_event():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    bus = EventBus()
    received = []
    bus.register(StudentAssessmentChanged, received.append)

    service = AssessmentService(factory, event_bus=bus)

    # The service validates only Assessment fields; a Student row is not required
    # for this in-memory event-contract test because SQLite FK enforcement is off.
    assessment = service.create_assessment(
        student_id=42,
        assessment_date=date(2026, 8, 26),
        assessment_type="Monthly",
        strengths="Strong logic",
        improvements="Practice more",
        next_goal="Complete mission",
    )

    assert len(received) == 1
    event = received[0]
    assert event.student_id == 42
    assert event.assessment_id == assessment.id
    assert event.action == "created"


def test_assessment_update_and_delete_are_report_relevant_contracts():
    service = Path("src/centermanager/services/assessment_service.py").read_text(encoding="utf-8")
    assert 'self._publish_assessment_changed(student_id, assessment.id, "created")' in service
    assert 'self._publish_assessment_changed(assessment.student_id, assessment.id, "updated")' in service
    assert 'self._publish_assessment_changed(student_id, assessment_id, "deleted")' in service


def test_mainwindow_marks_assessment_student_dirty():
    main = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
    assert "StudentAssessmentChanged" in main
    assert _has_main_window_event_registration(
        main,
        "StudentAssessmentChanged",
        "_on_student_assessment_changed_event",
    )
    start = main.index("def _on_student_assessment_changed_event")
    end = main.index("def _on_student_enrollment_changed_event", start)
    body = main[start:end]
    assert "self._transaction.mark_student_dirty(event.student_id)" in body


def test_post_publish_report_generation_uses_dirty_student_set():
    main = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
    assert "dirty_student_ids = list(self._transaction.dirty_student_ids)" in main
    assert 'trigger_event="student_updated"' in main
