# -*- coding: utf-8 -*-
"""
Database session management with context manager pattern.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, close_all_sessions, sessionmaker

from centermanager.database.engine import (
    begin_runtime_db_maintenance,
    create_production_engine,
    dispose_runtime_engines,
    end_runtime_db_maintenance,
    runtime_db_maintenance_active,
)


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
    """Fence and release process-owned runtime database handles.

    The application owns more than one production sessionmaker/Engine (notably
    the long-lived engine created by app.py). Merely disposing the engine bound
    to this module's global factory is therefore insufficient on Windows. The
    maintenance fence prevents retained/background sessionmakers from opening a
    new connection while all known Sessions and all tracked production Engines
    are being closed.

    The fence intentionally remains active after this function returns. The
    restore transaction releases it only through ``refresh_runtime_db()`` after
    either a successful filesystem swap or a completed rollback.
    """
    global _session_factory
    import logging

    logger = logging.getLogger(__name__)
    begin_runtime_db_maintenance()
    try:
        # Close caller-owned ORM sessions first. This returns checked-out SQLite
        # handles before disposing every production Engine registered by
        # database.engine, including app.py's independent engine.
        close_all_sessions()
        dispose_runtime_engines()
        _session_factory = None
    except Exception:
        # No destructive rename has happened yet when quiesce is entered from
        # BackupService, so do not strand the running app behind the fence.
        end_runtime_db_maintenance()
        raise

    logger.info("Runtime database connections quiesced under maintenance fence")


def refresh_runtime_db() -> None:
    """Re-enable runtime DB access and rebuild this module's session factory.

    Call only after the restore filesystem state is stable (success or rollback).
    Existing app-level sessionmakers remain valid because their tracked Engines
    are reusable after dispose; their guarded creators can reconnect only after
    the maintenance fence is released.
    """
    global _session_factory
    import logging

    # Be tolerant of callers outside restore: establish a quiesced state first.
    if not runtime_db_maintenance_active():
        quiesce_runtime_db()

    # The on-disk database is stable at this point. Release the fence before
    # create_production_engine(), whose lifecycle inspection legitimately opens
    # the restored runtime database.
    end_runtime_db_maintenance()
    _session_factory = create_session_factory()
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
