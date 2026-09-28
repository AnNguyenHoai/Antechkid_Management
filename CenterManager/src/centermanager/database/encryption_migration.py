# -*- coding: utf-8 -*-
"""One-time migration of a plaintext SQLite database to SQLCipher.

This module is deliberately not called implicitly from normal startup. Encryption
of the authoritative collaboration database is a controlled deployment action:
all authorized workstations must be provisioned with the same workspace key
before the encrypted repository artifact is published.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from centermanager.database.encryption import (
    DatabaseEncryptionError,
    apply_sqlcipher_key,
    is_plaintext_sqlite_file,
    load_sqlcipher_driver,
)


class DatabaseEncryptionMigrationError(DatabaseEncryptionError):
    """Raised when a plaintext-to-SQLCipher migration cannot complete safely."""


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _validate_encrypted_database(path: Path, key: bytes) -> None:
    sqlcipher = load_sqlcipher_driver()
    connection = sqlcipher.connect(str(path))
    try:
        apply_sqlcipher_key(connection, key)
        row = connection.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise DatabaseEncryptionMigrationError(
                f"Encrypted database integrity check failed: {row[0] if row else 'unknown'}"
            )
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    finally:
        connection.close()
    if is_plaintext_sqlite_file(path):
        raise DatabaseEncryptionMigrationError(
            "Migration output still exposes a plaintext SQLite header."
        )


def _promote_encrypted_database(temp_path: Path, database_path: Path, key: bytes) -> None:
    """Install a validated encrypted DB without losing the old DB or sidecars.

    Migration can encounter a live SQLite DB together with plaintext WAL/SHM
    sidecars.  Every live mutation therefore participates in the same rollback
    boundary.  Preserved artifacts are removed only after the installed
    encrypted database has itself passed validation.
    """
    previous_db = database_path.with_name(
        f".{database_path.name}.previous-{uuid.uuid4().hex}"
    )
    preserved_sidecars: list[tuple[Path, Path]] = []
    database_preserved = False
    database_installed = False

    try:
        # Preserve sidecars first. If any later move fails, already-preserved
        # artifacts are restored in reverse order below.
        for suffix in ("-wal", "-shm"):
            live = Path(str(database_path) + suffix)
            if not live.exists():
                continue
            preserved = database_path.parent / (
                f".{live.name}.previous-{uuid.uuid4().hex}"
            )
            os.replace(live, preserved)
            preserved_sidecars.append((live, preserved))

        os.replace(database_path, previous_db)
        database_preserved = True

        os.replace(temp_path, database_path)
        database_installed = True
        _validate_encrypted_database(database_path, key)
    except Exception:
        if database_installed and database_path.exists():
            database_path.unlink(missing_ok=True)
        if database_preserved and previous_db.exists():
            os.replace(previous_db, database_path)
        for live, preserved in reversed(preserved_sidecars):
            if preserved.exists():
                os.replace(preserved, live)
        raise

    # Commit the migration only after installed DB validation succeeds.
    previous_db.unlink(missing_ok=True)
    for _, preserved in preserved_sidecars:
        preserved.unlink(missing_ok=True)


def encrypt_plaintext_database_in_place(database_path: Path, key: bytes) -> Path:
    """Atomically replace a plaintext SQLite DB with SQLCipher ciphertext.

    The source DB is never overwritten until the encrypted temporary database
    has passed an integrity check with the supplied key. The caller must ensure
    no application process is concurrently writing the source database.
    """
    database_path = Path(database_path).resolve()
    if not database_path.is_file():
        raise DatabaseEncryptionMigrationError(
            f"Database does not exist: {database_path}"
        )
    if not is_plaintext_sqlite_file(database_path):
        # Idempotent success is allowed only when the existing DB can actually
        # be opened using the supplied SQLCipher key.
        _validate_encrypted_database(database_path, key)
        return database_path

    sqlcipher = load_sqlcipher_driver()
    temp_path = database_path.with_name(
        f".{database_path.name}.encrypted-{uuid.uuid4().hex}.tmp"
    )
    source = None
    try:
        # SQLCipher can open an ordinary SQLite DB when no key is supplied.
        source = sqlcipher.connect(str(database_path))
        integrity = source.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise DatabaseEncryptionMigrationError(
                "Plaintext source database failed integrity_check."
            )

        # Capture SQLite metadata not copied automatically by sqlcipher_export.
        user_version_row = source.execute("PRAGMA user_version").fetchone()
        user_version = int(user_version_row[0]) if user_version_row else 0

        # Fold committed WAL contents into the logical source before export.
        try:
            source.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
        except Exception:
            # Non-WAL databases legitimately reject/ignore checkpoint details.
            pass

        escaped_output = _escape_sql_literal(str(temp_path))
        source.execute(
            f"ATTACH DATABASE '{escaped_output}' AS encrypted "
            f"KEY \"x'{key.hex()}'\""
        )
        try:
            source.execute("SELECT sqlcipher_export('encrypted')").fetchone()
            source.execute(f"PRAGMA encrypted.user_version = {user_version}")
            target_integrity = source.execute(
                "PRAGMA encrypted.integrity_check"
            ).fetchone()
            if not target_integrity or target_integrity[0] != "ok":
                raise DatabaseEncryptionMigrationError(
                    "Encrypted migration target failed integrity_check."
                )
        finally:
            source.execute("DETACH DATABASE encrypted")
        source.close()
        source = None

        _validate_encrypted_database(temp_path, key)

        # Ensure encrypted bytes reach disk before the atomic promotion. On
        # Windows, os.fsync() requires a writable file descriptor.
        with temp_path.open("r+b") as handle:
            os.fsync(handle.fileno())

        _promote_encrypted_database(temp_path, database_path, key)
        return database_path
    except DatabaseEncryptionMigrationError:
        raise
    except Exception as exc:
        raise DatabaseEncryptionMigrationError(
            f"Database encryption migration failed: {exc}"
        ) from exc
    finally:
        if source is not None:
            try:
                source.close()
            except Exception:
                pass
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
