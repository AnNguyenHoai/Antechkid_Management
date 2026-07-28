# -*- coding: utf-8 -*-
"""
Tests for StudentRepository.
"""
import pytest
from sqlalchemy.orm import sessionmaker

from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.repositories.student_repository import StudentRepository


def test_add_student(test_db_path):
    """Test repository add operation."""
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    repo = StudentRepository(session)
    student = Student(student_code="HS001", full_name="Test Student")
    repo.add(student)
    session.commit()

    saved = repo.get_by_id(student.id)
    assert saved is not None
    assert saved.student_code == "HS001"


def test_get_by_code(test_db_path):
    """Test repository get_by_code."""
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    repo = StudentRepository(session)
    student = Student(student_code="HS001", full_name="Test Student")
    repo.add(student)
    session.commit()

    found = repo.get_by_code("HS001")
    assert found is not None
    assert found.id == student.id

    not_found = repo.get_by_code("HS999")
    assert not_found is None


def test_list_active_excludes_deleted(test_db_path):
    """Test list_active excludes soft-deleted students."""
    from datetime import datetime

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    repo = StudentRepository(session)

    active = Student(student_code="HS001", full_name="Active Student")
    deleted = Student(student_code="HS002", full_name="Deleted Student")
    deleted.deleted_at = datetime.now()

    repo.add(active)
    repo.add(deleted)
    session.commit()

    active_list = repo.list_active()
    assert len(active_list) == 1
    assert active_list[0].student_code == "HS001"


def test_list_all_including_deleted(test_db_path):
    """Test list_all_including_deleted returns all students."""
    from datetime import datetime

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    repo = StudentRepository(session)

    active = Student(student_code="HS001", full_name="Active")
    deleted = Student(student_code="HS002", full_name="Deleted")
    deleted.deleted_at = datetime.now()

    repo.add(active)
    repo.add(deleted)
    session.commit()

    all_students = repo.list_all_including_deleted()
    assert len(all_students) == 2