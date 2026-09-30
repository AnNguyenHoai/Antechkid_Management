# -*- coding: utf-8 -*-
"""
Database session management with context manager pattern.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, close_all_sessions, sessionmaker
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


def quiesce_runtime_db() -> None:
    """Release process-owned SQLAlchemy/SQLite handles to the runtime DB.

    Destructive recovery on Windows must close active ORM sessions and dispose
    the pooled engine *before* renaming ``center.db`` or its WAL/SHM sidecars.
    The global factory is cleared so no stale pooled connection can be reused.
    """
    global _session_factory
    import logging

    logger = logging.getLogger(__name__)
    factory = _session_factory

    # Close ORM sessions first so checked-out SQLite connections are returned to
    # the engine before the pool is disposed. This is intentionally process-wide
    # because restore is already protected by exclusive recovery authority.
    # Do not swallow failures here: recovery must fail before the destructive
    # rename if process-owned handles could not be released safely.
    close_all_sessions()

    try:
        if factory is not None:
            engine = factory.kw.get('bind')
            if engine is not None:
                engine.dispose()
    finally:
        # Never allow reuse of a factory that may still reference the pre-restore
        # database. A subsequent refresh will build a new factory/engine.
        _session_factory = None

    logger.info("Runtime database connections quiesced")


def refresh_runtime_db() -> None:
    """
    Refresh runtime database connections after database file replacement.
    This invalidates the global session factory and creates a new one.
    """
    global _session_factory
    quiesce_runtime_db()

    # Create new session factory only after the filesystem swap/rollback has
    # reached a stable state.
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
