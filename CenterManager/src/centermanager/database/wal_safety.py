# -*- coding: utf-8 -*-
"""WAL safety boundary for file-level publication of the live runtime database."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from centermanager.core.paths import get_paths
from centermanager.database.encryption import (
    DatabaseKeyStore,
    apply_sqlcipher_key,
    database_encryption_required,
    load_sqlcipher_driver,
)
from centermanager.database.engine import runtime_dbapi_connection


def _runtime_database_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=rw"


def checkpoint_runtime_database_for_publish() -> None:
    """Flush committed WAL frames into ``center.db`` before file-level publish.

    The runtime database is quiesced under the existing maintenance fence first,
    so no ORM/DBAPI handle can race the checkpoint or the subsequent file copy.
    A maintenance-owned connection performs ``wal_checkpoint(TRUNCATE)`` using
    the locally provisioned workspace key when SQLCipher is active. The normal
    session factory is rebuilt before this function returns.

    Any busy/incomplete checkpoint fails closed; callers must not publish a
    potentially stale ``center.db`` artifact.
    """
    # Lazy import avoids a module cycle: session -> engine, while this module
    # needs the session-level quiesce/refresh lifecycle.
    from centermanager.database.session import quiesce_runtime_db, refresh_runtime_db

    db_path = get_paths().database_dir / "center.db"
    if not db_path.exists():
        return

    encrypted = database_encryption_required()
    key = DatabaseKeyStore().load() if encrypted else None

    quiesce_runtime_db()
    try:
        def open_connection():
            if encrypted:
                sqlcipher = load_sqlcipher_driver()
                connection = sqlcipher.connect(
                    _runtime_database_uri(db_path),
                    uri=True,
                    check_same_thread=False,
                )
                try:
                    apply_sqlcipher_key(connection, key)  # type: ignore[arg-type]
                    connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
                    return connection
                except Exception:
                    connection.close()
                    raise
            return sqlite3.connect(
                _runtime_database_uri(db_path),
                uri=True,
                check_same_thread=False,
            )

        with runtime_dbapi_connection(
            open_connection,
            owner="write-publication-wal-checkpoint",
            maintenance_owned=True,
        ) as connection:
            row = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            # SQLite returns (busy, log_frames, checkpointed_frames). A non-zero
            # busy result means the main DB is not guaranteed to contain every
            # committed WAL frame and therefore cannot be published safely.
            if row is None or int(row[0]) != 0:
                raise RuntimeError(
                    f"Runtime WAL checkpoint incomplete; refusing publication: {row!r}"
                )
            connection.commit()
    finally:
        refresh_runtime_db()
