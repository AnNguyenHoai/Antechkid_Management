from centermanager.services.student_note_service import StudentNoteService


def test_student_note_service_bootstraps_without_explicit_provider():
    """Regression: legacy application composition must not fail at startup."""
    service = StudentNoteService(session_factory=None, timeline_service=None)
    assert service._repository_provider is not None
