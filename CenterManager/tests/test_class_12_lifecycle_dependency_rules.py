from pathlib import Path

CLASS_SERVICE = Path("src/centermanager/services/class_service.py").read_text(encoding="utf-8")
ENROLLMENT_SERVICE = Path("src/centermanager/services/enrollment_service.py").read_text(encoding="utf-8")
ASSIGNMENT_SERVICE = Path("src/centermanager/services/teacher_assignment_service.py").read_text(encoding="utf-8")
SESSION_SERVICE = Path("src/centermanager/services/session_service.py").read_text(encoding="utf-8")
REPOSITORY = Path("src/centermanager/repositories/class_repository.py").read_text(encoding="utf-8")


def test_archived_class_has_explicit_lifecycle_guard():
    assert "class ClassArchivedError" in CLASS_SERVICE
    assert "def _require_active_class" in CLASS_SERVICE
    assert "cannot be modified until restored" in CLASS_SERVICE


def test_archive_preserves_dependency_snapshot():
    assert "def _archive_snapshot" in CLASS_SERVICE
    assert "active_enrollments" in CLASS_SERVICE
    assert "teacher_assignments" in CLASS_SERVICE
    assert "sessions" in CLASS_SERVICE
    assert "dependency_snapshot" in CLASS_SERVICE


def test_archived_class_blocks_enrollment_and_assignment_mutations():
    assert "cannot change enrollments until restored" in ENROLLMENT_SERVICE
    assert "cannot change teacher assignments until restored" in ASSIGNMENT_SERVICE


def test_archived_class_blocks_session_mutations():
    assert "def _require_active_class" in SESSION_SERVICE
    assert "cannot change sessions until restored" in SESSION_SERVICE


def test_archived_classes_have_explicit_repository_and_service_read_paths():
    assert "def list_archived" in REPOSITORY
    assert "Class.deleted_at.is_not(None)" in REPOSITORY
    assert "def list_archived_classes" in CLASS_SERVICE
