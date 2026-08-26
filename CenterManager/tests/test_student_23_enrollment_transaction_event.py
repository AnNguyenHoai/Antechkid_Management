from pathlib import Path

EVENTS = Path("src/centermanager/events/student_events.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/enrollment_service.py").read_text(encoding="utf-8")
APP = Path("src/centermanager/app.py").read_text(encoding="utf-8")
MAIN = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")

def test_enrollment_domain_event_exists():
    assert "class StudentEnrollmentChanged(Event)" in EVENTS
    for field in ("student_id", "enrollment_id", "class_id", "action", "current_status"):
        assert field in EVENTS

def test_service_publishes_event_after_committed_enroll():
    assert "self._event_bus.publish(StudentEnrollmentChanged(" in SERVICE
    assert 'self._publish_change(enrollment, "ENROLLED", None)' in SERVICE

def test_service_publishes_event_after_committed_transitions():
    assert '"COMPLETED" if target == EnrollmentStatus.COMPLETED else "WITHDRAWN"' in SERVICE
    assert "previous_status" in SERVICE

def test_event_bus_is_injected_at_application_composition_root():
    assert "EnrollmentService(session_factory, event_bus=event_bus)" in APP

def test_main_window_subscribes_enrollment_event():
    assert "self._event_bus.register(StudentEnrollmentChanged, self._on_student_enrollment_changed_event)" in MAIN

def test_enrollment_event_marks_student_dirty_not_generic_only():
    start = MAIN.index("def _on_student_enrollment_changed_event")
    section = MAIN[start:MAIN.index("def _on_student_deleted_event", start)]
    assert "self._transaction.is_editing" in section
    assert "self._transaction.mark_student_dirty(event.student_id)" in section
