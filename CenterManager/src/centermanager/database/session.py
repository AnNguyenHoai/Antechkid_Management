# -*- coding: utf-8 -*-
"""
Database session management with context manager pattern.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import event

from centermanager.database.engine import create_production_engine


_session_factory = None


def create_session_factory(echo: bool = False) -> sessionmaker:
    """Create a session factory bound to the production engine."""
    engine = create_production_engine(echo=echo)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session_factory() -> sessionmaker:
    """Get or create the global session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory()
    return _session_factory


def refresh_runtime_db() -> None:
    """
    Refresh runtime database connections after database file replacement.
    This invalidates the global session factory and creates a new one.
    """
    global _session_factory
    # Dispose old engine
    try:
        if _session_factory is not None:
            engine = _session_factory.kw.get('bind')
            if engine is not None:
                engine.dispose()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to dispose old engine: {e}")
    
    # Create new session factory
    _session_factory = create_session_factory()
    import logging
    logging.getLogger(__name__).info("Runtime database session factory refreshed")


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
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()