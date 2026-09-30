# -*- coding: utf-8 -*-
"""Database session management with context manager pattern."""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, close_all_sessions, sessionmaker

from centermanager.database.engine import (
    begin_runtime_db_maintenance,
    close_runtime_dbapi_connections,
    create_production_engine,
    dispose_runtime_engines,
    end_runtime_db_maintenance,
    runtime_db_maintenance_active,
    runtime_dbapi_connection_count,
)

_session_factory = None


def create_session_factory(echo: bool = False) -> sessionmaker:
    engine = create_production_engine(echo=echo)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session_factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory()
    return _session_factory


def quiesce_runtime_db() -> None:
    """Fence access and prove zero process-owned DBAPI handles before restore."""
    global _session_factory
    import logging

    logger = logging.getLogger(__name__)
    begin_runtime_db_maintenance()
    try:
        # ORM Sessions are only one ownership layer. Production uses NullPool,
        # therefore a checked-out SQLAlchemy/raw DBAPI connection can outlive
        # Engine.dispose(). Drain all layers while the connection-creation fence
        # is held, then fail closed unless the registry is demonstrably empty.
        close_all_sessions()
        dispose_runtime_engines()
        close_runtime_dbapi_connections()
        remaining = runtime_dbapi_connection_count()
        if remaining:
            raise RuntimeError(
                f"Runtime database quiesce incomplete: {remaining} DBAPI handle(s) remain"
            )
        _session_factory = None
    except Exception:
        end_runtime_db_maintenance()
        raise

    logger.info(
        "Runtime database quiesced under maintenance fence; active DBAPI handles=0"
    )


def refresh_runtime_db() -> None:
    global _session_factory
    import logging

    if not runtime_db_maintenance_active():
        quiesce_runtime_db()
    end_runtime_db_maintenance()
    _session_factory = create_session_factory()
    logging.getLogger(__name__).info("Runtime database session factory refreshed")


@contextmanager
def session_scope(echo: bool = False) -> Generator[Session, None, None]:
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
