# -*- coding: utf-8 -*-
"""Database session management with context manager pattern."""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, close_all_sessions, sessionmaker

from centermanager.database.engine import (
    begin_runtime_db_maintenance,
    close_runtime_dbapi_connections,
    create_production_engine,
    dispose_runtime_engines,
    end_runtime_db_maintenance,
    get_database_path,
    runtime_db_maintenance_active,
    runtime_dbapi_connection_count,
    runtime_dbapi_connection_details,
)
from centermanager.platform.backup.windows_lock_diagnostics import (
    format_lock_owners,
    windows_lock_owners,
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


def quiesce_runtime_db(*, release_fence_on_failure: bool = True) -> None:
    """Fence access and prove zero process-owned DBAPI handles before restore.

    ``release_fence_on_failure`` is true for the initial pre-mutation quiesce so
    a failed restore attempt does not unnecessarily strand normal DB access. Once
    live restore mutation has started, callers pass false: failure to prove zero
    handles must then leave the process fenced rather than race a rollback rename.
    """
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
            details = runtime_dbapi_connection_details()
            summary = "; ".join(
                f"id={ident}, owner={info.owner}, thread={info.thread_id}"
                for ident, info in details
            )
            raise RuntimeError(
                f"Runtime database quiesce incomplete: {remaining} DBAPI handle(s) remain"
                + (f": {summary}" if summary else "")
            )
        _session_factory = None

        # The DBAPI registry proves only that CenterManager's guarded production
        # connection path is empty. On Windows, ask Restart Manager for the OS
        # truth before the destructive rename. This identifies both untracked
        # same-process handles and external processes without killing either.
        try:
            owners = windows_lock_owners(get_database_path())
        except Exception:
            logger.exception("Windows file-lock ownership diagnostics failed")
        else:
            if owners:
                same_process = [owner for owner in owners if owner.pid == os.getpid()]
                owner_text = format_lock_owners(owners)
                if same_process and runtime_dbapi_connection_count() == 0:
                    logger.error(
                        "UNTRACKED SAME-PROCESS HANDLE DETECTED for runtime DB: %s",
                        owner_text,
                    )
                    raise RuntimeError(
                        "Runtime database is still locked after quiesce; "
                        "UNTRACKED SAME-PROCESS HANDLE DETECTED; Windows lock owner(s): "
                        + owner_text
                    )
                raise RuntimeError(
                    "Runtime database is still locked after quiesce; Windows lock owner(s): "
                    + owner_text
                )
    except Exception:
        if release_fence_on_failure:
            end_runtime_db_maintenance()
        else:
            logger.error(
                "Runtime database quiesce failed after live restore mutation; "
                "maintenance fence remains enabled"
            )
        raise

    logger.info(
        "Runtime database quiesced under maintenance fence; active DBAPI handles=0"
    )


def refresh_runtime_db() -> None:
    """Rebuild the runtime session factory without leaving rollback unfenced.

    Creating the new production engine requires the maintenance fence to be
    released. If factory creation fails after that release, immediately
    re-quiesce before propagating the error so a restore caller can safely run
    its destructive rollback without a stale/reopened handle racing it.
    """
    global _session_factory
    import logging

    logger = logging.getLogger(__name__)
    if not runtime_db_maintenance_active():
        quiesce_runtime_db()

    _session_factory = None
    end_runtime_db_maintenance()
    try:
        new_factory = create_session_factory()
    except Exception:
        logger.exception(
            "Runtime database session factory rebuild failed; re-entering maintenance fence"
        )
        # create_session_factory() may have created/tracked an Engine or DBAPI
        # handle before failing. Re-quiesce drains any partial state and restores
        # the fence before restore_backup() attempts rollback rename/unlink. From
        # this point failure must keep the process fenced because live mutation
        # has already occurred.
        quiesce_runtime_db(release_fence_on_failure=False)
        raise

    _session_factory = new_factory
    logger.info("Runtime database session factory refreshed")


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
