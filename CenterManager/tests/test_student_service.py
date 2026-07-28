# -*- coding: utf-8 -*-
"""
Tests for StudentService.
"""
import pytest
from datetime import date, datetime, timezone
from unittest.mock import patch

from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.services.student_service import StudentService
from centermanager.services.exceptions import (
    StudentNotFoundError,
    StudentValidationError,
    StudentAlreadyDeletedError,
    StudentNotDeletedError,
)
from centermanager.models.student import Student
from centermanager.models.assessment import Assessment
from centermanager.repositories.student_repository import StudentRepository


def _utc_now():
    """Return naive UTC datetime (no timezone) for compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _create_service(test_db_path):
    """Create StudentService with test database."""
    from sqlalchemy.orm import sessionmaker
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return StudentService(session_factory)


# --- Code Generation Tests ---

def test_generate_code_empty_db(test_db_path):
    """Empty DB -> HS001."""
    service = _create_service(test_db_path)
    with service._session_factory() as session:
        code = service._generate_student_code(session)
        assert code == "HS001"


def test_generate_code_sequential(test_db_path):
    """HS001, HS002 -> HS003."""
    service = _create_service(test_db_path)
    service.create_student(full_name="Test 1")
    service.create_student(full_name="Test 2")
    with service._session_factory() as session:
        code = service._generate_student_code(session)
        assert code == "HS003"


def test_generate_code_skip(test_db_path):
    """HS001, HS005 -> HS006."""
    service = _create_service(test_db_path)
    service.create_student(full_name="Test 1")  # HS001
    # Manually create student with code HS005
    with service._session_factory() as session:
        s = Student(student_code="HS005", full_name="Test 5")
        session.add(s)
        session.commit()
    with service._session_factory() as session:
        code = service._generate_student_code(session)
        assert code == "HS006"


def test_generate_code_include_deleted(test_db_path):
    """HS001, HS002, HS003(deleted) -> HS004."""
    service = _create_service(test_db_path)
    s1 = service.create_student(full_name="Test 1")  # HS001
    s2 = service.create_student(full_name="Test 2")  # HS002
    s3 = service.create_student(full_name="Test 3")  # HS003
    # Soft delete s3
    with service._session_factory() as session:
        student = session.get(Student, s3.id)
        student.deleted_at = _utc_now()
        session.commit()
    with service._session_factory() as session:
        code = service._generate_student_code(session)
        assert code == "HS004"


def test_generate_code_legacy(test_db_path):
    """ABC, HS005, TEMP -> HS006."""
    service = _create_service(test_db_path)
    # Create legacy codes
    with service._session_factory() as session:
        legacy1 = Student(student_code="ABC", full_name="Legacy 1")
        legacy2 = Student(student_code="HS005", full_name="Legacy 2")
        legacy3 = Student(student_code="TEMP", full_name="Legacy 3")
        session.add_all([legacy1, legacy2, legacy3])
        session.commit()
    with service._session_factory() as session:
        code = service._generate_student_code(session)
        assert code == "HS006"


def test_generate_code_hs999_to_hs1000(test_db_path):
    """HS999 -> HS1000."""
    service = _create_service(test_db_path)
    with service._session_factory() as session:
        s = Student(student_code="HS999", full_name="Test 999")
        session.add(s)
        session.commit()
    with service._session_factory() as session:
        code = service._generate_student_code(session)
        assert code == "HS1000"


# --- Create Tests ---

def test_create_student(test_db_path):
    """Create valid student."""
    service = _create_service(test_db_path)
    student = service.create_student(
        full_name="Nguyen Van An",
        preferred_name="An",
        date_of_birth=date(2000, 1, 1),
        gender="MALE",
        status="ACTIVE",
        current_level="Beginner",
        notes="Good student"
    )
    assert student.id is not None
    assert student.student_code == "HS001"
    assert student.full_name == "Nguyen Van An"
    assert student.preferred_name == "An"
    assert student.date_of_birth == date(2000, 1, 1)
    assert student.gender == "MALE"
    assert student.status == "ACTIVE"
    assert student.current_level == "Beginner"
    assert student.notes == "Good student"
    assert student.created_at is not None
    assert student.updated_at is not None


def test_create_normalize_name(test_db_path):
    """full_name gets stripped."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="  Nguyễn Văn A  ")
    assert student.full_name == "Nguyễn Văn A"


def test_create_blank_full_name_fails(test_db_path):
    """Blank full_name raises validation error."""
    service = _create_service(test_db_path)
    with pytest.raises(StudentValidationError):
        service.create_student(full_name="")


def test_create_whitespace_full_name_fails(test_db_path):
    """Whitespace-only full_name raises validation error."""
    service = _create_service(test_db_path)
    with pytest.raises(StudentValidationError):
        service.create_student(full_name="   ")


def test_create_preferred_name_normalization(test_db_path):
    """preferred_name gets stripped; whitespace becomes None."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test", preferred_name="  An  ")
    assert student.preferred_name == "An"

    student2 = service.create_student(full_name="Test2", preferred_name="   ")
    assert student2.preferred_name is None


def test_create_default_status(test_db_path):
    """Default status is ACTIVE."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    assert student.status == "ACTIVE"


def test_create_explicit_status(test_db_path):
    """Explicit status is used."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test", status="INACTIVE")
    assert student.status == "INACTIVE"


# --- Get Tests ---

def test_get_student(test_db_path):
    """Get student by id."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    retrieved = service.get_student(student.id)
    assert retrieved.id == student.id
    assert retrieved.student_code == "HS001"


def test_get_student_not_found(test_db_path):
    """Get non-existent student raises NotFound."""
    service = _create_service(test_db_path)
    with pytest.raises(StudentNotFoundError):
        service.get_student(999)


def test_get_student_by_code(test_db_path):
    """Get student by student_code."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    retrieved = service.get_student_by_code("HS001")
    assert retrieved.id == student.id


def test_get_student_by_code_not_found(test_db_path):
    """Non-existent code raises NotFound."""
    service = _create_service(test_db_path)
    with pytest.raises(StudentNotFoundError):
        service.get_student_by_code("HS999")


# --- List Tests ---

def test_list_students(test_db_path):
    """list_students returns active students sorted by code."""
    service = _create_service(test_db_path)
    s1 = service.create_student(full_name="B Student")  # HS001
    s2 = service.create_student(full_name="A Student")  # HS002
    students = service.list_students()
    assert len(students) == 2
    assert students[0].student_code == "HS001"
    assert students[1].student_code == "HS002"


def test_list_excludes_deleted(test_db_path):
    """list_students excludes soft-deleted students."""
    service = _create_service(test_db_path)
    s1 = service.create_student(full_name="Test 1")
    s2 = service.create_student(full_name="Test 2")
    service.delete_student(s1.id)
    students = service.list_students()
    assert len(students) == 1
    assert students[0].id == s2.id


# --- Update Tests ---

def test_update_student_partial(test_db_path):
    """Partial update changes only supplied fields."""
    service = _create_service(test_db_path)
    student = service.create_student(
        full_name="Original Name",
        preferred_name="Nick",
        current_level="Beginner"
    )
    updated = service.update_student(student.id, current_level="Intermediate")
    assert updated.full_name == "Original Name"
    assert updated.preferred_name == "Nick"
    assert updated.current_level == "Intermediate"


def test_update_full_name_blank_fails(test_db_path):
    """Updating full_name to blank raises ValidationError."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    with pytest.raises(StudentValidationError):
        service.update_student(student.id, full_name="")


def test_update_student_code_not_allowed(test_db_path):
    """student_code cannot be updated."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    updated = service.update_student(student.id, notes="New note")
    assert updated.student_code == "HS001"


def test_update_clear_preferred_name(test_db_path):
    """Update preferred_name=None should clear the field."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test Student", preferred_name="Nick")
    updated = service.update_student(student.id, preferred_name=None)
    assert updated.preferred_name is None


def test_update_clear_date_of_birth(test_db_path):
    """Update date_of_birth=None should clear the field."""
    service = _create_service(test_db_path)
    dob = date(2000, 1, 1)
    student = service.create_student(full_name="Test Student", date_of_birth=dob)
    updated = service.update_student(student.id, date_of_birth=None)
    assert updated.date_of_birth is None


def test_update_without_date_of_birth_preserves(test_db_path):
    """Updating another field should not affect date_of_birth."""
    service = _create_service(test_db_path)
    dob = date(2000, 1, 1)
    student = service.create_student(full_name="Test Student", date_of_birth=dob)
    updated = service.update_student(student.id, notes="New note")
    assert updated.date_of_birth == dob
    assert updated.notes == "New note"


# --- Delete Tests ---

def test_delete_student(test_db_path):
    """Soft delete sets deleted_at."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    service.delete_student(student.id)

    # Check deleted_at is set
    with service._session_factory() as session:
        s = session.get(Student, student.id)
        assert s.deleted_at is not None

    # Should not appear in list
    assert len(service.list_students()) == 0

    # Normal get should raise NotFound
    with pytest.raises(StudentNotFoundError):
        service.get_student(student.id)


def test_delete_already_deleted_fails(test_db_path):
    """Deleting already-deleted raises AlreadyDeletedError."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    service.delete_student(student.id)
    with pytest.raises(StudentAlreadyDeletedError):
        service.delete_student(student.id)


def test_delete_not_found(test_db_path):
    """Deleting non-existent student raises NotFound."""
    service = _create_service(test_db_path)
    with pytest.raises(StudentNotFoundError):
        service.delete_student(999)


def test_delete_preserves_child_records(test_db_path):
    """
    Soft-deleting student should not delete child records (Assessment).
    This proves history preservation.
    """
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test Student")

    # Create an Assessment child record
    with service._session_factory() as session:
        assessment = Assessment(
            student_id=student.id,
            assessment_date=date(2026, 1, 1),
            cycle_months=3,
            level="Beginner",
            strengths="Good progress"
        )
        session.add(assessment)
        session.commit()

    # Delete student
    service.delete_student(student.id)

    # Check assessment still exists
    with service._session_factory() as session:
        assessment_exists = session.query(Assessment).filter(
            Assessment.student_id == student.id
        ).first()
        assert assessment_exists is not None
        assert assessment_exists.level == "Beginner"
        assert assessment_exists.strengths == "Good progress"


# --- Restore Tests ---

def test_restore_student(test_db_path):
    """Restore sets deleted_at = None."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    service.delete_student(student.id)
    service.restore_student(student.id)

    # Check deleted_at is None
    with service._session_factory() as session:
        s = session.get(Student, student.id)
        assert s.deleted_at is None

    # Should appear in list
    assert len(service.list_students()) == 1

    # Normal get works
    retrieved = service.get_student(student.id)
    assert retrieved.id == student.id


def test_restore_not_deleted_fails(test_db_path):
    """Restoring active student raises NotDeletedError."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    with pytest.raises(StudentNotDeletedError):
        service.restore_student(student.id)


def test_restore_not_found(test_db_path):
    """Restoring non-existent student raises NotFound."""
    service = _create_service(test_db_path)
    with pytest.raises(StudentNotFoundError):
        service.restore_student(999)


def test_delete_and_restore_preserves_code(test_db_path):
    """Restoring preserves original student_code."""
    service = _create_service(test_db_path)
    student = service.create_student(full_name="Test")
    original_code = student.student_code
    service.delete_student(student.id)
    service.restore_student(student.id)
    retrieved = service.get_student(student.id)
    assert retrieved.student_code == original_code


# --- Transaction Rollback Test ---

def test_transaction_rollback(test_db_path):
    """
    Prove that if an exception occurs after data is flushed inside a transaction,
    the transaction is rolled back and no partial data is committed.
    """
    service = _create_service(test_db_path)

    # Monkeypatch the repository's add method to simulate failure after flush
    # We'll patch StudentRepository.add to call original, then flush, then raise.
    original_add = StudentRepository.add

    def failing_add(repo_self, entity):
        # Add the entity to session (like original)
        repo_self.session.add(entity)
        # Force flush to write to DB (within transaction)
        repo_self.session.flush()
        # Now simulate an error after flush, before commit
        raise RuntimeError("Forced transaction failure")

    with patch.object(StudentRepository, 'add', failing_add):
        # Attempt to create student, should fail
        with pytest.raises(RuntimeError, match="Forced transaction failure"):
            service.create_student(full_name="Rollback Test")

    # Verify no student was created
    students = service.list_students()
    assert len(students) == 0, "Student should not exist after rollback"

    # Also verify directly in DB
    with service._session_factory() as session:
        count = session.query(Student).filter(Student.full_name == "Rollback Test").count()
        assert count == 0