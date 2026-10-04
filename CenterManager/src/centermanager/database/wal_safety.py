# -*- coding: utf-8 -*-
"""WAL safety boundary for file-level publication of the live runtime database."""
from __future__ import annotations

import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

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


def _checkpoint_runtime_database(db_path: Path, *, encrypted: bool, key: bytes | None) -> None:
    """Checkpoint the live runtime DB while the maintenance fence is already held."""

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


def checkpoint_runtime_database_for_publish() -> None:
    """Flush committed WAL frames into ``center.db`` and fail closed if incomplete.

    This compatibility entry point only guarantees that the checkpoint itself is
    protected by the maintenance fence. File-level publishers must use
    :func:`runtime_database_publication_snapshot` or
    :func:`copy_runtime_database_for_publish` so the source bytes are captured
    before the fence is released.
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
        _checkpoint_runtime_database(db_path, encrypted=encrypted, key=key)
    finally:
        refresh_runtime_db()


@contextmanager
def runtime_database_publication_snapshot() -> Iterator[Path]:
    """Yield an immutable, WAL-complete snapshot of the runtime ``center.db``.

    The critical invariant is that checkpoint **and snapshot capture** happen in
    one maintenance-fenced section. The live session factory is rebuilt only
    after the snapshot bytes are durable, eliminating the previous TOCTOU window
    where writers could resume between ``wal_checkpoint`` and the file copy.

    The yielded temporary file is stable even after the runtime database resumes
    normal activity and is deleted automatically when the context exits.
    """
    from centermanager.database.session import quiesce_runtime_db, refresh_runtime_db

    db_path = get_paths().database_dir / "center.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Runtime database not found: {db_path}")

    encrypted = database_encryption_required()
    key = DatabaseKeyStore().load() if encrypted else None
    snapshot = db_path.with_name(
        f".{db_path.name}.publish-snapshot-{uuid.uuid4().hex}.tmp"
    )

    quiesce_runtime_db()
    try:
        _checkpoint_runtime_database(db_path, encrypted=encrypted, key=key)
        shutil.copy2(db_path, snapshot)
        with snapshot.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        if snapshot.stat().st_size != db_path.stat().st_size:
            raise RuntimeError(
                "Runtime publication snapshot size mismatch; refusing publication"
            )
    except Exception:
        snapshot.unlink(missing_ok=True)
        raise
    finally:
        refresh_runtime_db()

    try:
        yield snapshot
    finally:
        snapshot.unlink(missing_ok=True)


def copy_runtime_database_for_publish(destination: Path) -> Path:
    """Atomically install a WAL-complete runtime DB snapshot at *destination*.

    The destination is first written to a sibling temporary file, fsynced, and
    only then replaced, so failures cannot leave a partially written authoritative
    Git artifact.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination_tmp = destination.with_name(
        f".{destination.name}.publish-copy-{uuid.uuid4().hex}.tmp"
    )

    try:
        with runtime_database_publication_snapshot() as snapshot:
            shutil.copy2(snapshot, destination_tmp)
            with destination_tmp.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
            if destination_tmp.stat().st_size != snapshot.stat().st_size:
                raise RuntimeError(
                    "Published database copy size mismatch; refusing installation"
                )
            os.replace(destination_tmp, destination)
    except Exception:
        destination_tmp.unlink(missing_ok=True)
        raise

    return destination
