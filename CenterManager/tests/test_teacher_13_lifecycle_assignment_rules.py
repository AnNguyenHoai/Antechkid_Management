from pathlib import Path

from centermanager.models.teacher import Teacher


def test_teacher_lifecycle_contract():
    assert Teacher.VALID_STATUSES == {"ACTIVE", "INACTIVE"}
    assert Teacher.STATUS_ACTIVE == "ACTIVE"
    assert Teacher.STATUS_INACTIVE == "INACTIVE"


def test_archived_teacher_is_not_active_and_cannot_accept_assignments():
    source = Path("src/centermanager/models/teacher.py").read_text(encoding="utf-8")
    assert "def is_archived" in source
    assert "def can_accept_new_assignments" in source
    assert "return self.is_active" in source


def test_teacher_service_validates_status_and_protects_archived_teacher():
    source = Path("src/centermanager/services/teacher_service.py").read_text(encoding="utf-8")
    assert "def _validate_status" in source
    assert "Teacher.VALID_STATUSES" in source
    assert "archived and must be restored before editing" in source
    assert "def list_archived_teachers" in source


def test_assignment_rules_reject_invalid_teacher_and_class_states():
    source = Path("src/centermanager/services/teacher_assignment_service.py").read_text(encoding="utf-8")
    assert "Archived teacher" in source
    assert "Inactive teacher" in source
    assert "Archived class" in source
    assert "Inactive class" in source
    assert "return ClassRepository(session).list_active()" in source
