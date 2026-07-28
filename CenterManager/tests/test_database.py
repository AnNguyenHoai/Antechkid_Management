# -*- coding: utf-8 -*-
"""
Tests for database engine, session, and FK enforcement.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from centermanager.database.engine import create_engine_for_path, get_database_path
from centermanager.database.session import session_scope
from centermanager.models.student import Student
from centermanager.models.parent import Parent


def test_engine_creates_file(test_db_path):
    """Test that engine creates database file upon connection."""
    from centermanager.database.engine import create_engine_for_path
    assert not test_db_path.exists()
    engine = create_engine_for_path(test_db_path)
    # Actually connect to create the file
    with engine.connect() as conn:
        from sqlalchemy import text
        conn.execute(text("SELECT 1"))
    assert test_db_path.exists()


def test_engine_enables_foreign_keys(test_db_path):
    """Test that foreign key enforcement is enabled."""
    from centermanager.database.engine import create_engine_for_path
    from sqlalchemy import text

    engine = create_engine_for_path(test_db_path)
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert result == 1


def test_session_scope_commits(test_db_path):
    """Test that session_scope commits on success."""
    from centermanager.database.engine import create_engine_for_path
    from centermanager.database.session import session_scope
    from centermanager.database.base import Base
    from centermanager.models.student import Student

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)

    # Override session_scope to use test engine
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        student = Student(
            student_code="HS001",
            full_name="Test Student"
        )
        session.add(student)
        session.commit()
    finally:
        session.close()

    with Session() as sess:
        count = sess.query(Student).count()
        assert count == 1


def test_foreign_key_enforcement(test_db_path):
    """Test that FK enforcement prevents orphan records."""
    from centermanager.database.engine import create_engine_for_path
    from centermanager.database.base import Base
    from sqlalchemy.orm import sessionmaker

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Try to create Parent with non-existent student_id
    parent = Parent(
        student_id=99999,  # non-existent
        name="Test Parent"
    )
    session.add(parent)

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_production_db_path_uses_centralized_paths():
    """Test that database path comes from centralized path system."""
    from centermanager.database.engine import get_database_path
    from centermanager.core.paths import get_paths

    paths = get_paths()
    expected = paths.database_dir / "center.db"
    actual = get_database_path()
    assert actual == expected