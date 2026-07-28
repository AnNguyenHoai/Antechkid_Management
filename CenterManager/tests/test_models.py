# -*- coding: utf-8 -*-
"""
Tests for all 8 ORM models and relationships.
"""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models import *


def test_student_model(test_db_path):
    """Test Student model creation and constraints."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(
        student_code="HS001",
        full_name="Nguyen Van An"
    )
    session.add(student)
    session.commit()

    saved = session.get(Student, student.id)
    assert saved.student_code == "HS001"
    assert saved.full_name == "Nguyen Van An"
    assert saved.status == "ACTIVE"
    assert saved.created_at is not None
    assert saved.updated_at is not None


def test_student_unique_code(test_db_path):
    """Test that student_code must be unique."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    s1 = Student(student_code="HS001", full_name="Student 1")
    s2 = Student(student_code="HS001", full_name="Student 2")

    session.add(s1)
    session.commit()

    session.add(s2)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_parent_relationship(test_db_path):
    """Test Student-Parent relationship."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(student_code="HS001", full_name="Test Student")

    # Tạo Parent và gán student object
    parent1 = Parent(
        name="Parent One",
        is_primary_contact=True,
        student=student  # Gán student object, SQLAlchemy sẽ tự set student_id
    )
    parent2 = Parent(
        name="Parent Two",
        is_primary_contact=False,
        student=student
    )

    session.add(student)
    session.add(parent1)
    session.add(parent2)
    session.commit()

    saved = session.get(Student, student.id)
    assert len(saved.parents) == 2
    assert saved.parents[0].student_id == student.id
    assert saved.parents[1].student_id == student.id


def test_enrollment_relationship(test_db_path):
    """Test Student-Enrollment relationship."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(student_code="HS001", full_name="Test Student")
    enrollment1 = Enrollment(class_name="Python 101", student=student)
    enrollment2 = Enrollment(class_name="Robotics", student=student)

    session.add(student)
    session.add(enrollment1)
    session.add(enrollment2)
    session.commit()

    saved = session.get(Student, student.id)
    assert len(saved.enrollments) == 2


def test_assessment_relationship(test_db_path):
    """Test multiple assessments per student."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(student_code="HS001", full_name="Test Student")
    
    # Đúng: gán student object qua relationship
    assessment1 = Assessment(cycle_months=3, level="Beginner", student=student)
    assessment2 = Assessment(cycle_months=6, level="Intermediate", student=student)

    session.add(student)
    session.add(assessment1)
    session.add(assessment2)
    session.commit()

    saved = session.get(Student, student.id)
    assert len(saved.assessments) == 2


def test_timeline_event_relationship(test_db_path):
    """Test Student-TimelineEvent relationship."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(student_code="HS001", full_name="Test Student")
    event = TimelineEvent(event_type="ACHIEVEMENT", title="Completed Python Project", student=student)
    session.add(student)
    session.add(event)
    session.commit()

    saved = session.get(Student, student.id)
    assert len(saved.timeline_events) == 1
    assert saved.timeline_events[0].title == "Completed Python Project"


def test_student_product_relationship(test_db_path):
    """Test StudentProduct relationship."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(student_code="HS001", full_name="Test Student")
    product = StudentProduct(
        title="Robot Warehouse",
        product_type="Scratch",
        url="https://scratch.mit.edu/projects/123",
        student=student
    )

    session.add(student)
    session.add(product)
    session.commit()

    saved = session.get(Student, student.id)
    assert len(saved.products) == 1
    assert saved.products[0].url == "https://scratch.mit.edu/projects/123"


def test_progress_relationship(test_db_path):
    """Test Progress relationship."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(student_code="HS001", full_name="Test Student")
    
    # Đúng: gán student object qua relationship
    progress1 = Progress(category="Python", value=80, student=student)
    progress2 = Progress(category="Robotics", value=60, student=student)

    session.add(student)
    session.add(progress1)
    session.add(progress2)
    session.commit()

    saved = session.get(Student, student.id)
    assert len(saved.progress_records) == 2


def test_attachment_model(test_db_path):
    """Test Attachment model with relative path."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(student_code="HS001", full_name="Test Student")
    attachment = Attachment(
        file_name="portfolio.pdf",
        file_type="pdf",
        relative_path="HS001/portfolio.pdf",
        description="Student portfolio",
        student=student
    )

    session.add(student)
    session.add(attachment)
    session.commit()

    saved = session.get(Student, student.id)
    assert len(saved.attachments) == 1
    assert saved.attachments[0].relative_path == "HS001/portfolio.pdf"


def test_soft_delete_field(test_db_path):
    """Test that Student has deleted_at field."""
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    student = Student(student_code="HS001", full_name="Test Student")
    session.add(student)
    session.commit()

    saved = session.get(Student, student.id)
    assert saved.deleted_at is None

    saved.deleted_at = datetime.now()
    session.commit()

    updated = session.get(Student, student.id)
    assert updated.deleted_at is not None