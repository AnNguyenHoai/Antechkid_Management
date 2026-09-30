# -*- coding: utf-8 -*-
import logging
import sqlite3
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable, Iterator
from urllib.parse import quote
from weakref import WeakSet

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from centermanager.core.paths import get_paths
from centermanager.database.encryption import (
    DatabaseKeyStore,
    apply_sqlcipher_key,
    database_encryption_required,
    load_sqlcipher_driver,
)
from centermanager.database.lifecycle import DatabaseLifecycle, DatabaseLifecycleState
from centermanager.security.protected_storage import assert_direct_database_access_allowed

logger = logging.getLogger(__name__)

_runtime_db_gate = RLock()
_runtime_db_maintenance = False
_runtime_engines: WeakSet[Engine] = WeakSet()
_runtime_dbapi_connections: dict[int, object] = {}


@dataclass(frozen=True)
class RuntimeDatabaseHandleInfo:
    """Diagnostic metadata for one process-owned handle to the live runtime DB."""

    owner: str
    thread_id: int
    opened_at: float
    stack: str


_runtime_dbapi_connection_info: dict[int, RuntimeDatabaseHandleInfo] = {}


class RuntimeDatabaseMaintenanceError(RuntimeError):
    """Raised when runtime DB access is attempted during destructive recovery."""


def runtime_db_maintenance_active() -> bool:
    with _runtime_db_gate:
        return _runtime_db_maintenance


def runtime_dbapi_connection_count() -> int:
    with _runtime_db_gate:
        return len(_runtime_dbapi_connections)


def runtime_dbapi_connection_details() -> list[tuple[int, RuntimeDatabaseHandleInfo]]:
    """Return a stable diagnostic snapshot of all currently tracked handles."""
    with _runtime_db_gate:
        active_ids = set(_runtime_dbapi_connections)
        return [
            (ident, info)
            for ident, info in _runtime_dbapi_connection_info.items()
            if ident in active_ids
        ]


def _register_runtime_dbapi_connection(connection: object, *, owner: str = "unknown") -> None:
    ident = id(connection)
    with _runtime_db_gate:
        _runtime_dbapi_connections[ident] = connection
        _runtime_dbapi_connection_info[ident] = RuntimeDatabaseHandleInfo(
            owner=str(owner or "unknown"),
            thread_id=threading.get_ident(),
            opened_at=time.time(),
            stack="".join(traceback.format_stack(limit=12)[:-1]),
        )


def _unregister_runtime_dbapi_connection(connection: object) -> None:
    ident = id(connection)
    with _runtime_db_gate:
        _runtime_dbapi_connections.pop(ident, None)
        _runtime_dbapi_connection_info.pop(ident, None)


def acquire_runtime_dbapi_connection(
    opener: Callable[[], object],
    *,
    owner: str,
) -> object:
    """Atomically open and register a handle to the live runtime database.

    Every direct live ``center.db`` open outside SQLAlchemy should use this
    boundary. The maintenance gate is held across both the OS-level open and
    registry insertion, so once maintenance begins there can be no invisible
    race where a new live handle exists but quiesce cannot see it.
    """
    with _runtime_db_gate:
        if _runtime_db_maintenance:
            raise RuntimeDatabaseMaintenanceError(
                "Runtime database is temporarily unavailable during backup restore"
            )
        connection = opener()
        _register_runtime_dbapi_connection(connection, owner=owner)
        return connection


def release_runtime_dbapi_connection(connection: object) -> None:
    """Close a tracked runtime handle and unregister only after close succeeds.

    Recovery may force-close a registered handle while its owner is unwinding.
    In that case the handle has already been natively closed and removed, so the
    owner must not issue a second driver ``close()`` against an invalid object.
    """
    with _runtime_db_gate:
        if id(connection) not in _runtime_dbapi_connections:
            return
    connection.close()  # type: ignore[attr-defined]
    _unregister_runtime_dbapi_connection(connection)


@contextmanager
def runtime_dbapi_connection(
    opener: Callable[[], object],
    *,
    owner: str,
) -> Iterator[object]:
    """Context-manager form of the process-wide runtime DB ownership boundary."""
    connection = acquire_runtime_dbapi_connection(opener, owner=owner)
    try:
        yield connection
    finally:
        release_runtime_dbapi_connection(connection)


def close_runtime_dbapi_connections() -> None:
    """Force-close every tracked production DBAPI connection, fail closed."""
    with _runtime_db_gate:
        connections = list(_runtime_dbapi_connections.values())
    failures = []
    closed = 0
    for connection in connections:
        try:
            connection.close()  # type: ignore[attr-defined]
        except Exception as exc:
            failures.append((id(connection), exc))
            logger.exception("Failed to close tracked production DBAPI handle id=%s", id(connection))
        else:
            _unregister_runtime_dbapi_connection(connection)
            closed += 1
    if failures:
        remaining = runtime_dbapi_connection_count()
        details = ", ".join(f"id={ident}: {exc}" for ident, exc in failures)
        raise RuntimeDatabaseMaintenanceError(
            f"Failed to close {len(failures)} runtime database handle(s); "
            f"{remaining} handle(s) remain registered: {details}"
        )
    remaining = runtime_dbapi_connection_count()
    if remaining:
        raise RuntimeDatabaseMaintenanceError(
            f"Runtime database quiesce incomplete: {remaining} DBAPI handle(s) remain"
        )
    logger.info("Closed %d tracked production DBAPI connection(s)", closed)


def begin_runtime_db_maintenance() -> None:
    global _runtime_db_maintenance
    with _runtime_db_gate:
        if _runtime_db_maintenance:
            return
        _runtime_db_maintenance = True
    logger.info("Runtime database maintenance fence enabled")


def end_runtime_db_maintenance() -> None:
    global _runtime_db_maintenance
    with _runtime_db_gate:
        _runtime_db_maintenance = False
    logger.info("Runtime database maintenance fence disabled")


def dispose_runtime_engines() -> None:
    with _runtime_db_gate:
        engines = list(_runtime_engines)
    for engine in engines:
        engine.dispose()
    logger.info("Disposed %d tracked production database engine(s)", len(engines))


def get_database_path() -> Path:
    return get_paths().database_dir / "center.db"


def _database_uri(db_path: Path, *, allow_create: bool, readonly: bool = False) -> str:
    mode = "ro" if readonly else ("rwc" if allow_create else "rw")
    return f"file:{quote(db_path.resolve().as_posix(), safe='/:')}?mode={mode}"


def _connect_plain(
    db_path: Path,
    *,
    allow_create: bool,
    readonly: bool = False,
):
    return sqlite3.connect(
        _database_uri(db_path, allow_create=allow_create, readonly=readonly),
        uri=True,
        check_same_thread=False,
    )


def _connect_encrypted(
    db_path: Path,
    key: bytes,
    *,
    allow_create: bool,
    readonly: bool = False,
    runtime_guarded: bool = False,
    owner: str = "encrypted-runtime",
):
    """Open SQLCipher, optionally under the process-wide runtime ownership gate."""

    def open_connection():
        sqlcipher = load_sqlcipher_driver()
        connection = sqlcipher.connect(
            _database_uri(db_path, allow_create=allow_create, readonly=readonly),
            uri=True,
            check_same_thread=False,
        )
        try:
            apply_sqlcipher_key(connection, key)
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
            return connection
        except Exception:
            connection.close()
            raise

    if not runtime_guarded:
        return open_connection()
    return acquire_runtime_dbapi_connection(open_connection, owner=owner)


class _TrackedLifecycleConnection:
    """Small adapter that keeps lifecycle close ordering fail-closed."""

    def __init__(self, raw, *, owner: str):
        self._raw = raw
        ident = id(raw)
        with _runtime_db_gate:
            if ident in _runtime_dbapi_connections:
                return
            if _runtime_db_maintenance:
                try:
                    raw.close()
                finally:
                    raise RuntimeDatabaseMaintenanceError(
                        "Runtime database is temporarily unavailable during backup restore"
                    )
            _register_runtime_dbapi_connection(raw, owner=owner)

    def execute(self, *args, **kwargs):
        return self._raw.execute(*args, **kwargs)

    def close(self):
        release_runtime_dbapi_connection(self._raw)


def _runtime_lifecycle(
    db_path: Path,
    key: bytes | None = None,
    *,
    runtime_guarded: bool = False,
) -> DatabaseLifecycle:
    if key is None:
        if not runtime_guarded:
            return DatabaseLifecycle(db_path)

        def readonly_plain_connector(path: Path):
            raw = acquire_runtime_dbapi_connection(
                lambda: _connect_plain(path, allow_create=False, readonly=True),
                owner="runtime-lifecycle-plain",
            )
            return _TrackedLifecycleConnection(raw, owner="runtime-lifecycle-plain")

        return DatabaseLifecycle(db_path, readonly_connector=readonly_plain_connector)

    def readonly_encrypted_connector(path: Path):
        connection = _connect_encrypted(
            path,
            key,
            allow_create=False,
            readonly=True,
            runtime_guarded=runtime_guarded,
        )
        if not runtime_guarded:
            return connection
        return _TrackedLifecycleConnection(connection, owner="runtime-lifecycle-encrypted")

    return DatabaseLifecycle(db_path, readonly_connector=readonly_encrypted_connector)


def inspect_runtime_database() -> DatabaseLifecycleState:
    assert_direct_database_access_allowed()
    db_path = get_database_path()
    if not database_encryption_required():
        return _runtime_lifecycle(db_path, runtime_guarded=True).inspect()
    try:
        key = DatabaseKeyStore().load()
    except Exception:
        logger.exception("Encrypted runtime database key is unavailable")
        return DatabaseLifecycleState.RECOVERY_REQUIRED
    return _runtime_lifecycle(db_path, key, runtime_guarded=True).inspect()


def create_engine_for_path(
    db_path: Path,
    echo: bool = False,
    *,
    allow_create: bool = True,
    encrypted: bool = False,
    encryption_key: bytes | None = None,
    runtime_guarded: bool = False,
) -> Engine:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if encrypted and encryption_key is None:
        raise ValueError("encryption_key is required for an encrypted database")
    lifecycle = _runtime_lifecycle(
        db_path,
        encryption_key if encrypted else None,
        runtime_guarded=runtime_guarded,
    )

    def open_connection():
        if not allow_create:
            lifecycle.require_available()
        if encrypted:
            return _connect_encrypted(
                db_path,
                encryption_key,  # type: ignore[arg-type]
                allow_create=allow_create,
                runtime_guarded=False,
            )
        return _connect_plain(db_path, allow_create=allow_create)

    def connect_database():
        if not runtime_guarded:
            return open_connection()
        return acquire_runtime_dbapi_connection(open_connection, owner="sqlalchemy-runtime-engine")

    engine = create_engine("sqlite://", echo=echo, creator=connect_database, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def set_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    # SQLAlchemy's PoolEvents.close fires *before* dialect.do_close().
    # Unregistering in that event creates a false-zero window where the registry
    # says the handle is gone while Windows still sees the native SQLite handle.
    # Wrap the dialect close boundary instead and unregister only after the
    # driver's close/terminate call succeeds.
    original_do_close = engine.dialect.do_close
    original_do_terminate = engine.dialect.do_terminate

    def tracked_do_close(dbapi_connection):
        original_do_close(dbapi_connection)
        _unregister_runtime_dbapi_connection(dbapi_connection)

    def tracked_do_terminate(dbapi_connection):
        original_do_terminate(dbapi_connection)
        _unregister_runtime_dbapi_connection(dbapi_connection)

    engine.dialect.do_close = tracked_do_close  # type: ignore[method-assign]
    engine.dialect.do_terminate = tracked_do_terminate  # type: ignore[method-assign]

    return engine


def initialize_runtime_database() -> Path:
    assert_direct_database_access_allowed()
    db_path = get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        return db_path
    if database_encryption_required():
        key = DatabaseKeyStore().load_or_create(allow_create=True)
        connection = _connect_encrypted(db_path, key, allow_create=True)
    else:
        connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.commit()
    finally:
        connection.close()
    logger.info("Initialized new runtime database container (encrypted=%s)", database_encryption_required())
    return db_path


def create_production_engine(echo: bool = False) -> Engine:
    assert_direct_database_access_allowed()
    with _runtime_db_gate:
        if _runtime_db_maintenance:
            raise RuntimeDatabaseMaintenanceError(
                "Runtime database is temporarily unavailable during backup restore"
            )
        db_path = get_database_path()
        encrypted = database_encryption_required()
        key = DatabaseKeyStore().load() if encrypted else None
        state = _runtime_lifecycle(
            db_path,
            key if encrypted else None,
            runtime_guarded=True,
        ).inspect()
        if state is not DatabaseLifecycleState.AVAILABLE:
            logger.warning(
                "Runtime database is not currently available: state=%s; recovery is required before first use",
                state.value,
            )
        engine = create_engine_for_path(
            db_path,
            echo=echo,
            allow_create=False,
            encrypted=encrypted,
            encryption_key=key,
            runtime_guarded=True,
        )
        _runtime_engines.add(engine)
        return engine
