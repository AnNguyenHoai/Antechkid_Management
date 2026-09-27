# -*- coding: utf-8 -*-
"""Security boundary for database artifacts outside the live SQLAlchemy engine.

Git repository copies and backup/restore paths are file-level artifacts. In
production they must remain SQLCipher ciphertext and must authenticate with the
locally provisioned shared workspace key before they are accepted or published.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from centermanager.core.paths import get_paths
from centermanager.database.encryption import (
    DatabaseEncryptionError,
    DatabaseKeyStore,
    apply_sqlcipher_key,
    database_encryption_required,
    is_plaintext_sqlite_file,
    load_sqlcipher_driver,
)


class DatabaseArtifactSecurityError(DatabaseEncryptionError):
    """Raised when a runtime/repository DB artifact violates security policy."""


def _validate_plain_database(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise DatabaseArtifactSecurityError(f"Database artifact is missing or empty: {path}")
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise DatabaseArtifactSecurityError(f"Invalid SQLite database artifact: {path}") from exc
    if not row or row[0] != "ok":
        raise DatabaseArtifactSecurityError(
            f"SQLite integrity check failed for {path}: {row[0] if row else 'unknown'}"
        )


def validate_database_artifact(
    path: Path,
    *,
    encryption_required: Optional[bool] = None,
    key: Optional[bytes] = None,
) -> None:
    """Validate a DB artifact under the active runtime security policy."""
    path = Path(path)
    encrypted = database_encryption_required() if encryption_required is None else encryption_required
    if not encrypted:
        _validate_plain_database(path)
        return

    if not path.is_file() or path.stat().st_size == 0:
        raise DatabaseArtifactSecurityError(f"Encrypted database artifact is missing or empty: {path}")
    if is_plaintext_sqlite_file(path):
        raise DatabaseArtifactSecurityError(
            f"Plaintext SQLite artifact is forbidden in production: {path}"
        )
    workspace_key = key if key is not None else DatabaseKeyStore().load()
    try:
        sqlcipher = load_sqlcipher_driver()
        connection = sqlcipher.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            apply_sqlcipher_key(connection, workspace_key)
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except DatabaseEncryptionError:
        raise
    except Exception as exc:
        raise DatabaseArtifactSecurityError(
            f"Encrypted database artifact cannot be authenticated with the workspace key: {path}"
        ) from exc
    if not row or row[0] != "ok":
        raise DatabaseArtifactSecurityError(
            f"SQLCipher integrity check failed for {path}: {row[0] if row else 'unknown'}"
        )


def authoritative_repository_database_path() -> Path:
    paths = get_paths()
    return paths.runtime_root / "repository" / "database" / "center.db"


def validate_authoritative_repository_database() -> Path:
    """Fail closed if the Git source-of-truth DB violates active policy."""
    repo_db = authoritative_repository_database_path()
    validate_database_artifact(repo_db)
    return repo_db


def materialize_runtime_database_to_repository() -> Path:
    """Atomically publish the current runtime DB into the Git working tree.

    Validation occurs before and after the copy. In encrypted production mode
    this guarantees both source and authoritative repository artifact are
    SQLCipher ciphertext authenticated by the shared workspace key. The temp
    artifact is ciphertext because this is a byte-for-byte file materialization.
    """
    paths = get_paths()
    runtime_db = paths.database_dir / "center.db"
    repo_db = authoritative_repository_database_path()
    encrypted = database_encryption_required()
    key = DatabaseKeyStore().load() if encrypted else None

    validate_database_artifact(runtime_db, encryption_required=encrypted, key=key)
    repo_db.parent.mkdir(parents=True, exist_ok=True)
    tmp = repo_db.with_name(f".{repo_db.name}.publish-{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(runtime_db, tmp)
        with tmp.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        validate_database_artifact(tmp, encryption_required=encrypted, key=key)
        os.replace(tmp, repo_db)
        validate_database_artifact(repo_db, encryption_required=encrypted, key=key)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return repo_db
