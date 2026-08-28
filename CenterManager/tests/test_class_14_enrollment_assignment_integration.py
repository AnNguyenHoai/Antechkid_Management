from pathlib import Path

CLASS_SERVICE = Path("src/centermanager/services/class_service.py").read_text(encoding="utf-8")
ENROLLMENT_SERVICE = Path("src/centermanager/services/enrollment_service.py").read_text(encoding="utf-8")
ASSIGNMENT_DIALOG = Path("src/centermanager/ui/class_workspace/class_assignment_dialog.py").read_text(encoding="utf-8")
ENROLLMENT_DIALOG = Path("src/centermanager/ui/class_workspace/class_enrollment_dialog.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/class_workspace/class_detail_page.py").read_text(encoding="utf-8")


def test_class_facade_preserves_shared_event_bus_for_enrollment():
    assert "EnrollmentService(self._session_factory, event_bus=self._event_bus)" in CLASS_SERVICE
    assert "StudentEnrollmentChanged" in ENROLLMENT_SERVICE


def test_class_facade_preserves_shared_event_bus_for_assignment():
    assert "TeacherAssignmentService(" in CLASS_SERVICE
    assert "event_bus=self._event_bus" in CLASS_SERVICE


def test_archived_enrollment_transition_has_defined_validation_error():
    assert "class EnrollmentValidationError" in ENROLLMENT_SERVICE


def test_assignment_dialog_emits_change_after_successful_mutation():
    assert "assignment_changed = Signal(int)" in ASSIGNMENT_DIALOG
    assert ASSIGNMENT_DIALOG.count("assignment_changed.emit(self._class_id)") >= 2


def test_enrollment_dialog_emits_change_after_successful_mutation():
    assert "enrollment_changed = Signal(int)" in ENROLLMENT_DIALOG
    assert ENROLLMENT_DIALOG.count("enrollment_changed.emit(self._class_id)") >= 2


def test_detail_page_integrates_dialog_mutation_signals():
    assert "dialog.assignment_changed.connect(self._on_assignment_changed)" in DETAIL
    assert "dialog.enrollment_changed.connect(self._on_enrollment_changed)" in DETAIL
    assert "def _on_assignment_changed" in DETAIL
    assert "def _on_enrollment_changed" in DETAIL
