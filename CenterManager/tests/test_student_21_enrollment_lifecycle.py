from pathlib import Path

MODEL = Path("src/centermanager/models/enrollment.py").read_text(encoding="utf-8")
REPO = Path("src/centermanager/repositories/enrollment_repository.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/enrollment_service.py").read_text(encoding="utf-8")
CLASS = Path("src/centermanager/services/class_service.py").read_text(encoding="utf-8")

def test_enrollment_has_safe_active_default():
    assert 'default="ACTIVE"' in MODEL
    assert 'server_default="ACTIVE"' in MODEL

def test_lifecycle_statuses_are_explicit():
    for value in ("ACTIVE", "COMPLETED", "WITHDRAWN"):
        assert value in SERVICE

def test_duplicate_rule_is_active_only():
    assert "def exists(self, student_id: int, class_id: int, active_only: bool = True)" in REPO
    assert 'Enrollment.status == "ACTIVE"' in REPO

def test_capacity_counts_active_enrollments_only():
    assert "get_active_by_class" in REPO
    assert "len(repo.get_active_by_class(class_id))" in SERVICE

def test_transition_only_from_active():
    assert 'if enrollment.status != EnrollmentStatus.ACTIVE.value:' in SERVICE
    assert "InvalidEnrollmentTransitionError" in SERVICE

def test_withdraw_and_complete_preserve_history():
    assert "def withdraw(" in SERVICE
    assert "def complete(" in SERVICE
    assert "self._session.delete" not in SERVICE

def test_legacy_class_service_delegates_to_canonical_service():
    section = CLASS[CLASS.index("def enroll_student"):CLASS.index("def get_enrolled_students")]
    assert "EnrollmentService" in section
    assert "service.withdraw(enrollment_id)" in section
    assert "enroll_repo.delete(enrollment)" not in section

def test_enrolled_student_list_is_active_only():
    section = CLASS[CLASS.index("def get_enrolled_students"):CLASS.index("# ===== Teacher Assignment")]
    assert 'e.status == "ACTIVE"' in section
