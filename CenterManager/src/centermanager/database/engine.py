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

# SEC06 destructive restore must fence *every* production engine, not only the
# session factory owned by database.session. app.py also creates a long-lived
# production engine/sessionmaker and background services may retain it. A
# disposed SQLAlchemy Engine is reusable, so disposal alone is not a fence: its
# creator must reject new connections until the filesystem swap/rollback is
# complete.
_runtime_db_gate = RLock()
_runtime_db_maintenance = False
_runtime_engines: WeakSet[Engine] = WeakSet()


class RuntimeDatabaseMaintenanceError(RuntimeError):
    """Raised when runtime DB access is attempted during destructive recovery."""


def runtime_db_maintenance_active() -> bool:
    with _runtime_db_gate:
        return _runtime_db_maintenance


def begin_runtime_db_maintenance() -> None:
    """Fence creation of new production DB connections.

    Taking the same gate used by guarded engine creators waits for any
    connection currently being opened to finish before maintenance becomes
    active. After this function returns, existing connections may be closed and
    engines disposed without a new production connection racing the restore.
    """
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
    """Return the runtime database path without creating the database file."""
    return get_paths().database_dir / "center.db"


def _database_uri(db_path: Path, *, allow_create: bool, readonly: bool = False) -> str:
    if readonly:
        mode = "ro"
    else:
        mode = "rwc" if allow_create else "rw"
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
    """Inspect the runtime DB using the same encryption boundary as production.

    Missing/unreadable key material fails closed as RECOVERY_REQUIRED rather
    than retrying with plain SQLite. In SEC-02 enforced mode the desktop process
    is forbidden from opening the database directly at all.
    """
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
    """Create a database engine for a specific path.

    The historical low-level helper remains plain SQLite by default so tests
    can create disposable databases. Production explicitly enables encryption
    on Windows and never falls back to stdlib SQLite if SQLCipher/key loading
    fails. Production engines opt into ``runtime_guarded`` so an old retained
    sessionmaker cannot reopen ``center.db`` during destructive restore.
    """
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
                db_path,
                encryption_key,  # type: ignore[arg-type]
                allow_create=allow_create,
            )
        return sqlite3.connect(
            _database_uri(db_path, allow_create=allow_create),
            uri=True,
            check_same_thread=False,
        )

    def connect_database():
        if not runtime_guarded:
            return open_connection()
        # Hold the gate through the actual OS open. begin_runtime_db_maintenance
        # therefore cannot return while a connection creation is in-flight.
        with _runtime_db_gate:
            if _runtime_db_maintenance:
                raise RuntimeDatabaseMaintenanceError(
                    "Runtime database is temporarily unavailable during backup restore"
                )
            return open_connection()

    engine = create_engine(
        "sqlite://",
        echo=echo,
        creator=connect_database,
        poolclass=NullPool,
    )

    @event.listens_for(engine, "connect")
    def set_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    return engine


def initialize_runtime_database() -> Path:
    """Create the runtime database container during explicit first-run setup.

    Windows production creates a SQLCipher database and a random 256-bit DB key
    protected by DPAPI. Existing database files are never overwritten and a
    missing key for an existing DB is never silently replaced. SEC-02 enforced
    mode forbids this desktop-owned initialization path.
    """
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
    """Create a tracked, maintenance-fenced production engine."""
    assert_direct_database_access_allowed()

    # Serialize engine construction/lifecycle inspection against the start of a
    # destructive restore. This prevents an engine from slipping into existence
    # between the maintenance check and registration.
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
