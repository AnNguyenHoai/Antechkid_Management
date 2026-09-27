# -*- coding: utf-8 -*-
import logging
import sqlite3
from pathlib import Path
from urllib.parse import quote

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

logger = logging.getLogger(__name__)


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
        # Force SQLCipher to read the encrypted schema immediately. A wrong key
        # therefore fails at the connection boundary rather than much later.
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
    than retrying with plain SQLite.
    """
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
) -> Engine:
    """Create a database engine for a specific path.

    The historical low-level helper remains plain SQLite by default so tests
    can create disposable databases. Production explicitly enables encryption
    on Windows and never falls back to stdlib SQLite if SQLCipher/key loading
    fails.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if encrypted and encryption_key is None:
        raise ValueError("encryption_key is required for an encrypted database")

    lifecycle = _runtime_lifecycle(db_path, encryption_key if encrypted else None)

    def connect_database():
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
    missing key for an existing DB is never silently replaced.
    """
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
    """Create production engine without auto-creating DB or encryption keys."""
    db_path = get_database_path()
    encrypted = database_encryption_required()
    key = DatabaseKeyStore().load() if encrypted else None
    state = _runtime_lifecycle(db_path, key if encrypted else None).inspect()

    if state is not DatabaseLifecycleState.AVAILABLE:
        logger.warning(
            "Runtime database is not currently available: state=%s; recovery is required before first use",
            state.value,
        )
    return create_engine_for_path(
        db_path,
        echo=echo,
        allow_create=False,
        encrypted=encrypted,
        encryption_key=key,
    )
