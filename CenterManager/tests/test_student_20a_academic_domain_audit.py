from pathlib import Path

ROOT = Path("src/centermanager")

ENROLLMENT = (ROOT / "models/enrollment.py").read_text(encoding="utf-8")
STUDENT = (ROOT / "models/student.py").read_text(encoding="utf-8")
CLASS = (ROOT / "models/class_.py").read_text(encoding="utf-8")
REPO = (ROOT / "repositories/enrollment_repository.py").read_text(encoding="utf-8")
CLASS_SERVICE = (ROOT / "services/class_service.py").read_text(encoding="utf-8")
ATTENDANCE = (ROOT / "services/attendance_service.py").read_text(encoding="utf-8")


def test_enrollment_is_already_the_student_class_association():
    assert 'student_id' in ENROLLMENT
    assert 'class_id' in ENROLLMENT
    assert 'relationship("Student", back_populates="enrollments")' in ENROLLMENT
    assert 'relationship("Class", back_populates="enrollments")' in ENROLLMENT


def test_student_and_class_expose_the_same_enrollment_association():
    assert 'enrollments' in STUDENT
    assert 'enrollments' in CLASS


def test_existing_repository_is_the_data_boundary_for_student_class_lookup():
    assert "def get_by_student" in REPO
    assert "def get_by_class" in REPO
    assert "def exists" in REPO


def test_existing_class_service_already_owns_legacy_enrollment_operations():
    assert "def enroll_student" in CLASS_SERVICE
    assert "def remove_student" in CLASS_SERVICE


def test_attendance_depends_on_enrollment_eligibility_for_session_date():
    assert "_check_student_enrolled" in ATTENDANCE
    # EP-ATT-02 keeps Enrollment as the attendance eligibility boundary, but the
    # canonical production path is now historical/date-aware instead of checking
    # only today's ACTIVE enrollment. Lightweight legacy providers may still use
    # the narrow exists(...) fallback for dependency-injection compatibility.
    assert "_is_student_eligible_for_session" in ATTENDANCE
    assert "get_by_student_and_class" in ATTENDANCE
    assert "_enrollment_covers_session_date" in ATTENDANCE
    assert 'getattr(session_obj, "scheduled_date", None)' in ATTENDANCE
    assert 'exists = getattr(enrollment_repo, "exists", None)' in ATTENDANCE


def test_enrollment_has_existing_lifecycle_fields_to_formalize():
    assert "start_date" in ENROLLMENT
    assert "end_date" in ENROLLMENT
    assert "status" in ENROLLMENT


def test_no_course_aggregate_is_required_by_current_architecture():
    # Class currently stores course as metadata, so Student 2.0 must not create
    # a parallel Course FK before a dedicated Course-domain decision.
    assert 'course:' in CLASS
    assert 'Mapped[Optional[str]]' in CLASS
