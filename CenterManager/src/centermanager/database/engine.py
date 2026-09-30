# -*- coding: utf-8 -*-
import logging
import sqlite3
from pathlib import Path
from threading import RLock
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
# DBAPI connection objects (sqlite3 / SQLCipher) are not weak-referenceable on
# every supported driver, so keep an identity keyed registry. Production uses
# NullPool: Engine.dispose() cannot be treated as proof that a checked-out raw
# connection no longer owns center.db on Windows.
_runtime_dbapi_connections: dict[int, object] = {}


class RuntimeDatabaseMaintenanceError(RuntimeError):
    """Raised when runtime DB access is attempted during destructive recovery."""


def runtime_db_maintenance_active() -> bool:
    with _runtime_db_gate:
        return _runtime_db_maintenance


def runtime_dbapi_connection_count() -> int:
    """Return the number of process-owned production DBAPI handles."""
    with _runtime_db_gate:
        return len(_runtime_dbapi_connections)


def _register_runtime_dbapi_connection(connection: object) -> None:
    with _runtime_db_gate:
        _runtime_dbapi_connections[id(connection)] = connection


def _unregister_runtime_dbapi_connection(connection: object) -> None:
    with _runtime_db_gate:
        _runtime_dbapi_connections.pop(id(connection), None)


def close_runtime_dbapi_connections() -> None:
    """Force-close every tracked production DBAPI connection.

    This runs only after the maintenance fence is active, so no guarded
    production creator can add another handle while the registry is drained.
    A handle is removed from the registry only after close() succeeds.  This is
    deliberately fail-closed: on Windows a failed close can still own center.db,
    so reporting zero handles would make a destructive os.replace unsafe.
    """
    with _runtime_db_gate:
        connections = list(_runtime_dbapi_connections.values())
    failures = []
    closed = 0
    for connection in connections:
        try:
            connection.close()  # type: ignore[attr-defined]
        except Exception as exc:
            # Preserve failed handles in the registry.  Recovery callers can then
            # distinguish a real quiescent process from a close attempt that failed.
            failures.append((id(connection), exc))
            logger.exception(
                "Failed to close tracked production DBAPI handle id=%s",
                id(connection),
            )
        else:
            _unregister_runtime_dbapi_connection(connection)
            closed += 1
    if failures:
        remaining = runtime_dbapi_connection_count()
        details = ", ".join(f"id={ident}: {exc}" for ident, exc in failures)
        raise RuntimeDatabaseMaintenanceError(
            "Failed to close "
            f"{len(failures)} runtime database handle(s); "
            f"{remaining} handle(s) remain registered: {details}"
        )
    remaining = runtime_dbapi_connection_count()
    if remaining:
        raise RuntimeDatabaseMaintenanceError(
            f"Runtime database quiesce incomplete: {remaining} DBAPI handle(s) remain"
        )
    logger.info("Closed %d tracked production DBAPI connection(s)", closed)


def begin_runtime_db_maintenance() -> None:
    """Fence creation of new production DB connections."""
    global _runtime_db_maintenance
    with _runtime_db_gate:
        if _runtime_db_maintenance:
            return
        _runtime_db_maintenance = True
    logger.info("Runtime database maintenance fence enabled")


def end_runtime_db_maintenance() -> None:
    """Allow production DB connections after a stable swap or rollback."""
    global _runtime_db_maintenance
    with _runtime_db_gate:
        _runtime_db_maintenance = False
    logger.info("Runtime database maintenance fence disabled")


def dispose_runtime_engines() -> None:
    """Dispose every production Engine created by this process."""
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


def _connect_encrypted(db_path: Path, key: bytes, *, allow_create: bool, readonly: bool = False):
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


def _runtime_lifecycle(db_path: Path, key: bytes | None = None) -> DatabaseLifecycle:
    if key is None:
        return DatabaseLifecycle(db_path)

    def readonly_connector(path: Path):
        return _connect_encrypted(path, key, allow_create=False, readonly=True)

    return DatabaseLifecycle(db_path, readonly_connector=readonly_connector)


def inspect_runtime_database() -> DatabaseLifecycleState:
    assert_direct_database_access_allowed()
    db_path = get_database_path()
    if not database_encryption_required():
        return DatabaseLifecycle(db_path).inspect()
    try:
        key = DatabaseKeyStore().load()
    except Exception:
        logger.exception("Encrypted runtime database key is unavailable")
        return DatabaseLifecycleState.RECOVERY_REQUIRED
    return _runtime_lifecycle(db_path, key).inspect()


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
    lifecycle = _runtime_lifecycle(db_path, encryption_key if encrypted else None)

    def open_connection():
        if not allow_create:
            lifecycle.require_available()
        if encrypted:
            return _connect_encrypted(
                db_path, encryption_key, allow_create=allow_create  # type: ignore[arg-type]
            )
        return sqlite3.connect(
            _database_uri(db_path, allow_create=allow_create),
            uri=True,
            check_same_thread=False,
        )

    def connect_database():
        if not runtime_guarded:
            return open_connection()
        # Hold the gate through OS open *and* registry insertion. Once
        # begin_runtime_db_maintenance() returns, every pre-existing production
        # handle is visible to close_runtime_dbapi_connections().
        with _runtime_db_gate:
            if _runtime_db_maintenance:
                raise RuntimeDatabaseMaintenanceError(
                    "Runtime database is temporarily unavailable during backup restore"
                )
            connection = open_connection()
            _runtime_dbapi_connections[id(connection)] = connection
            return connection

    engine = create_engine(
        "sqlite://", echo=echo, creator=connect_database, poolclass=NullPool
    )

    @event.listens_for(engine, "connect")
    def set_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    @event.listens_for(engine, "close")
    def unregister_closed_connection(dbapi_connection, connection_record):
        _unregister_runtime_dbapi_connection(dbapi_connection)

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
    logger.info(
        "Initialized new runtime database container (encrypted=%s)",
        database_encryption_required(),
    )
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
        state = _runtime_lifecycle(db_path, key if encrypted else None).inspect()
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
