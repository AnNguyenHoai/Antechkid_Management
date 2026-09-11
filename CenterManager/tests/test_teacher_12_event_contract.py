from dataclasses import is_dataclass
from pathlib import Path

from centermanager.events.event import Event
from centermanager.events.teacher_events import (
    TeacherCreated, TeacherUpdated, TeacherArchived, TeacherRestored,
    TeacherAssignmentChanged, TeacherDocumentChanged,
)


def test_teacher_event_types_are_domain_events():
    event_types = [
        TeacherCreated, TeacherUpdated, TeacherArchived, TeacherRestored,
        TeacherAssignmentChanged, TeacherDocumentChanged,
    ]
    assert all(issubclass(t, Event) for t in event_types)
    assert all(is_dataclass(t) for t in event_types)


def test_teacher_service_event_contract_is_present():
    text = Path("src/centermanager/services/teacher_service.py").read_text(encoding="utf-8")
    for event_name in ("TeacherCreated", "TeacherUpdated", "TeacherArchived", "TeacherRestored"):
        assert f"publish({event_name}" in text
    assert text.index("session.commit()") < text.index("publish(TeacherCreated")
    assert text.index("session.commit()") < text.index("publish(TeacherArchived")


def test_assignment_and_document_events_are_present():
    assignment = Path("src/centermanager/services/teacher_assignment_service.py").read_text(encoding="utf-8")
    document = Path("src/centermanager/services/teacher_document_service.py").read_text(encoding="utf-8")
    assert "publish(TeacherAssignmentChanged" in assignment
    assert 'action="assigned"' in assignment
    assert 'action="unassigned"' in assignment
    assert "publish(TeacherDocumentChanged" in document
    assert 'action="uploaded"' in document
    assert 'action="deleted"' in document


def test_app_composition_uses_shared_event_bus():
    text = Path("src/centermanager/app.py").read_text(encoding="utf-8")
    assert "TeacherService(" in text and "event_bus=event_bus" in text
    assert "TeacherAssignmentService(" in text
    assert "TeacherDocumentService(" in text
