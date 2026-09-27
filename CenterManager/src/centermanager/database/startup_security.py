# -*- coding: utf-8 -*-
"""Fail-closed startup preflight for the authoritative database artifact.

Normal application startup must never invent a replacement workspace key or
implicitly encrypt the collaboration database. Encryption/key distribution is a
controlled deployment operation because every authorized workstation must share
the same workspace key.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from centermanager.database.artifact_security import (
    DatabaseArtifactSecurityError,
    validate_database_artifact,
)
from centermanager.database.encryption import (
    DatabaseKeyStore,
    database_encryption_required,
    is_plaintext_sqlite_file,
)


class StartupDatabaseReadiness(str, Enum):
    READY = "ready"
    MISSING = "missing"
    PLAINTEXT_MIGRATION_REQUIRED = "plaintext_migration_required"
    KEY_PROVISIONING_REQUIRED = "key_provisioning_required"
    KEY_UNAVAILABLE = "key_unavailable"
    KEY_MISMATCH_OR_CORRUPT = "key_mismatch_or_corrupt"


@dataclass(frozen=True)
class StartupDatabasePreflight:
    state: StartupDatabaseReadiness
    message: str

    @property
    def ready(self) -> bool:
        return self.state is StartupDatabaseReadiness.READY


def inspect_authoritative_database_for_startup(path: Path) -> StartupDatabasePreflight:
    """Classify the Git-authoritative DB before it is copied into runtime.

    The check deliberately distinguishes a plaintext migration requirement from
    a missing/unusable shared key. This avoids the previous ambiguous
    ``recovery_required`` result and, more importantly, prevents startup from
    creating a fresh key that could never decrypt an already-encrypted database.
    """
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        return StartupDatabasePreflight(
            StartupDatabaseReadiness.MISSING,
            "Authoritative repository database is missing or empty.",
        )

    if not database_encryption_required():
        try:
            validate_database_artifact(path, encryption_required=False)
        except Exception as exc:
            return StartupDatabasePreflight(
                StartupDatabaseReadiness.KEY_MISMATCH_OR_CORRUPT,
                f"Authoritative database failed integrity validation: {exc}",
            )
        return StartupDatabasePreflight(
            StartupDatabaseReadiness.READY,
            "Authoritative database is ready.",
        )

    if is_plaintext_sqlite_file(path):
        return StartupDatabasePreflight(
            StartupDatabaseReadiness.PLAINTEXT_MIGRATION_REQUIRED,
            "Authoritative database is plaintext SQLite. Run the controlled SEC-01 "
            "workspace encryption migration before production startup; normal startup "
            "will not generate a key or publish an implicit migration.",
        )

    key_store = DatabaseKeyStore()
    if not key_store.bundle_path.is_file():
        return StartupDatabasePreflight(
            StartupDatabaseReadiness.KEY_PROVISIONING_REQUIRED,
            "Authoritative database is encrypted but this Windows profile has no "
            "workspace database key bundle. Provision the existing shared workspace "
            "key; do not generate a new key for this database.",
        )

    try:
        key = key_store.load()
    except Exception as exc:
        return StartupDatabasePreflight(
            StartupDatabaseReadiness.KEY_UNAVAILABLE,
            f"Workspace database key bundle exists but cannot be unprotected: {exc}",
        )

    try:
        validate_database_artifact(path, encryption_required=True, key=key)
    except DatabaseArtifactSecurityError as exc:
        return StartupDatabasePreflight(
            StartupDatabaseReadiness.KEY_MISMATCH_OR_CORRUPT,
            "Authoritative encrypted database cannot be authenticated with the "
            f"provisioned workspace key: {exc}",
        )
    except Exception as exc:
        return StartupDatabasePreflight(
            StartupDatabaseReadiness.KEY_MISMATCH_OR_CORRUPT,
            f"Authoritative encrypted database validation failed: {exc}",
        )

    return StartupDatabasePreflight(
        StartupDatabaseReadiness.READY,
        "Authoritative encrypted database and workspace key are ready.",
    )
