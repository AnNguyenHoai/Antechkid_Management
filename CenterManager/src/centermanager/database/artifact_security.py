# -*- coding: utf-8 -*-
"""Security boundary for database artifacts outside the live SQLAlchemy engine.

Git repository copies and backup/restore paths are file-level artifacts. In
production they must remain SQLCipher ciphertext and must authenticate with the
locally provisioned shared workspace key before they are accepted or published.
The Git-authoritative DB additionally carries a signed stable identity and
monotonic generation so decryptability alone is not treated as provenance.
"""
from __future__ import annotations

import filecmp
import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from centermanager.core.paths import get_paths
from centermanager.database.artifact_identity import (
    DatabaseArtifactIdentityError,
    identity_manifest_path,
    next_identity_document,
    validate_and_pin_identity,
    write_identity_document,
)
from centermanager.database.encryption import (
    DatabaseEncryptionError,
    DatabaseKeyStore,
    apply_sqlcipher_key,
    database_encryption_required,
    is_plaintext_sqlite_file,
    load_sqlcipher_driver,
)
from centermanager.database.engine import runtime_dbapi_connection
from centermanager.database.wal_safety import runtime_database_publication_snapshot


class DatabaseArtifactSecurityError(DatabaseEncryptionError):
    """Raised when a runtime/repository DB artifact violates security policy."""


def _validate_plain_database(path: Path, *, runtime_guarded: bool = False) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise DatabaseArtifactSecurityError(f"Database artifact is missing or empty: {path}")

    def open_connection():
        return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)

    try:
        if runtime_guarded:
            with runtime_dbapi_connection(
                open_connection,
                owner="artifact-security-plain-validation",
            ) as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
        else:
            connection = open_connection()
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
    runtime_guarded: bool = False,
) -> None:
    """Validate a DB artifact under the active runtime security policy.

    ``runtime_guarded`` must be true when *path* is the live runtime ``center.db``.
    Repository, staged-restore and temporary artifacts remain intentionally
    outside the runtime ownership registry because they cannot block replacement
    of the live database file.
    """
    path = Path(path)
    encrypted = database_encryption_required() if encryption_required is None else encryption_required
    if not encrypted:
        _validate_plain_database(path, runtime_guarded=runtime_guarded)
        return

    if not path.is_file() or path.stat().st_size == 0:
        raise DatabaseArtifactSecurityError(f"Encrypted database artifact is missing or empty: {path}")
    if is_plaintext_sqlite_file(path):
        raise DatabaseArtifactSecurityError(
            f"Plaintext SQLite artifact is forbidden in production: {path}"
        )
    workspace_key = key if key is not None else DatabaseKeyStore().load()

    def open_connection():
        sqlcipher = load_sqlcipher_driver()
        connection = sqlcipher.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            apply_sqlcipher_key(connection, workspace_key)
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
            return connection
        except Exception:
            connection.close()
            raise

    try:
        if runtime_guarded:
            with runtime_dbapi_connection(
                open_connection,
                owner="artifact-security-encrypted-validation",
            ) as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
        else:
            connection = open_connection()
            try:
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
    """Fail closed if the Git source-of-truth DB violates active policy.

    Disposable non-production synchronization tests historically use providers
    without materializing a physical database. Preserve that test/dev contract;
    production encryption mode still treats a missing artifact as a hard error.
    """
    repo_db = authoritative_repository_database_path()
    encrypted = database_encryption_required()
    if not encrypted and not repo_db.exists():
        return repo_db

    key = DatabaseKeyStore().load() if encrypted else None
    validate_database_artifact(repo_db, encryption_required=encrypted, key=key)
    if encrypted:
        try:
            validate_and_pin_identity(repo_db, key)
        except DatabaseArtifactIdentityError as exc:
            raise DatabaseArtifactSecurityError(
                f"Authoritative database identity validation failed: {exc}"
            ) from exc
    return repo_db


def _publish_encrypted_repository_pair(
    source_tmp: Path,
    repo_db: Path,
    key: bytes,
) -> None:
    """Install DB + signed identity as one rollback-safe publication boundary.

    A legacy transaction path may have already copied the validated runtime DB
    over ``repo_db`` before this security boundary is reached. In that narrow
    case the old signed sidecar no longer matches the repository bytes. Permit
    identity rotation only when the repository bytes are *exactly identical* to
    ``source_tmp`` (which was copied from and validated against the runtime DB).
    Any other identity mismatch remains fail-closed.
    """
    manifest = identity_manifest_path(repo_db)

    if repo_db.exists() and manifest.exists():
        validate_database_artifact(repo_db, encryption_required=True, key=key)
        try:
            validate_and_pin_identity(repo_db, key)
        except DatabaseArtifactIdentityError:
            if not filecmp.cmp(repo_db, source_tmp, shallow=False):
                raise

    identity_document = next_identity_document(source_tmp, key, repo_db)
    identity_tmp = manifest.with_name(f".{manifest.name}.publish-{uuid.uuid4().hex}.tmp")
    write_identity_document(identity_tmp, identity_document)

    previous_db = repo_db.with_name(f".{repo_db.name}.previous-{uuid.uuid4().hex}")
    previous_manifest = manifest.with_name(f".{manifest.name}.previous-{uuid.uuid4().hex}")
    db_preserved = False
    manifest_preserved = False
    db_installed = False
    manifest_installed = False
    try:
        if repo_db.exists():
            os.replace(repo_db, previous_db)
            db_preserved = True
        if manifest.exists():
            os.replace(manifest, previous_manifest)
            manifest_preserved = True

        os.replace(source_tmp, repo_db)
        db_installed = True
        os.replace(identity_tmp, manifest)
        manifest_installed = True

        validate_database_artifact(repo_db, encryption_required=True, key=key)
        validate_and_pin_identity(repo_db, key)
    except Exception:
        if manifest_installed and manifest.exists():
            manifest.unlink(missing_ok=True)
        if db_installed and repo_db.exists():
            repo_db.unlink(missing_ok=True)
        if manifest_preserved and previous_manifest.exists():
            os.replace(previous_manifest, manifest)
        if db_preserved and previous_db.exists():
            os.replace(previous_db, repo_db)
        raise
    finally:
        identity_tmp.unlink(missing_ok=True)

    previous_db.unlink(missing_ok=True)
    previous_manifest.unlink(missing_ok=True)


def materialize_runtime_database_to_repository() -> Path:
    """Atomically publish the current runtime DB into the Git working tree.

    Validation and publication operate on an immutable WAL-complete snapshot.
    In encrypted production mode the repository DB is also published together
    with a signed stable identity, exact SHA-256 and monotonic generation. A
    failure installing either half restores the previous authoritative pair.
    """
    paths = get_paths()
    runtime_db = paths.database_dir / "center.db"
    repo_db = authoritative_repository_database_path()
    encrypted = database_encryption_required()

    if not encrypted and not runtime_db.exists():
        return repo_db

    key = DatabaseKeyStore().load() if encrypted else None

    # Preserve the security boundary before WAL checkpointing. In particular,
    # plaintext production artifacts must be classified as a security-policy
    # violation rather than leaking a lower-level SQLCipher "not a database"
    # error from the checkpoint connection. This preflight is not the publication
    # authority: the immutable snapshot is validated again below after capture.
    validate_database_artifact(
        runtime_db,
        encryption_required=encrypted,
        key=key,
        runtime_guarded=True,
    )

    repo_db.parent.mkdir(parents=True, exist_ok=True)
    tmp = repo_db.with_name(f".{repo_db.name}.publish-{uuid.uuid4().hex}.tmp")
    try:
        # Checkpoint and snapshot capture occur inside one maintenance-fenced
        # boundary. The yielded file remains stable after live runtime activity
        # resumes, so validation/copy cannot race a new WAL checkpoint.
        with runtime_database_publication_snapshot() as runtime_snapshot:
            validate_database_artifact(
                runtime_snapshot,
                encryption_required=encrypted,
                key=key,
            )
            shutil.copy2(runtime_snapshot, tmp)

        with tmp.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        validate_database_artifact(tmp, encryption_required=encrypted, key=key)

        if encrypted:
            _publish_encrypted_repository_pair(tmp, repo_db, key)
            tmp = None
        else:
            os.replace(tmp, repo_db)
            tmp = None
            validate_database_artifact(repo_db, encryption_required=False)
    except Exception:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        raise
    return repo_db
