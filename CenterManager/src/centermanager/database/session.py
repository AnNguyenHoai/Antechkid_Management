# -*- coding: utf-8 -*-
"""
Database session management with context manager pattern.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from centermanager.database.engine import create_production_engine


def create_session_factory(echo: bool = False) -> sessionmaker:
    """Create a session factory bound to the production engine."""
    engine = create_production_engine(echo=echo)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def session_scope(echo: bool = False) -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            session.add(some_object)
            # commit on success, rollback on failure

    Args:
        echo: Enable SQL echo for debugging.

    Yields:
        SQLAlchemy Session object.
    """
    session = create_session_factory(echo=echo)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()