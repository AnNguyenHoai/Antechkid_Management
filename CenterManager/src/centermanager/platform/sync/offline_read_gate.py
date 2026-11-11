# -*- coding: utf-8 -*-
"""STARTUP-FIX-01 Phase 1: non-mutating eligibility check for cached READ.

This probe does not fetch Git, inspect historical Recovery, migrate schema
or grant WRITE authority. A separate machine-key-signed accepted-MAIN cache
is minimum proof; simply finding center.db is not enough.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OfflineReadEligibility:
    allowed: bool
    reason: str


def assess_offline_read(paths=None) -> OfflineReadEligibility:
    """Fail closed unless the already accepted runtime is safe to observe.

    No fall back on incomplete first installations, unaccepted local edits,
    malformed recovery material, changed SQLCipher artifacts, or WAL files.
    """
    from centermanager.core.paths import get_paths
    from centermanager.database.engine import inspect_runtime_database
    from centermanager.database.lifecycle import DatabaseLifecycleState
    from centermanager.database.encryption import DatabaseKeyStore, database_encryption_required
    from centermanager.database.artifact_security import validate_database_artifact
    from centermanager.database.artifact_identity import validate_identity
    from centermanager.platform.sync.offline_main_receipt import (
        verify_authenticated_cache,
    )

    paths = paths or get_paths()
    db = Path(paths.database_dir) / "center.db"
    repo_db = Path(paths.runtime_root) / "repository" / "database" / "center.db"
    try:
        if not verify_authenticated_cache(paths):
            return OfflineReadEligibility(
                False, "Independent signed Git MAIN offline cache is unavailable."
            )
        if not db.is_file() or not repo_db.is_file() or db.stat().st_size == 0:
            return OfflineReadEligibility(False, "Accepted runtime/repository database is missing.")
        if db.is_symlink() or repo_db.is_symlink():
            return OfflineReadEligibility(False, "Database symlink cannot be trusted.")
        if any(db.with_name(db.name + suffix).exists() for suffix in ("-wal", "-journal")):
            return OfflineReadEligibility(False, "Uncheckpointed database state requires recovery.")
        # Cache authentication already bound both hashes to the secret
        # protected database key, independent from Recovery review state.

        encrypted = database_encryption_required()
        key = DatabaseKeyStore().load() if encrypted else None
        validate_database_artifact(db, encryption_required=encrypted, key=key)
        validate_database_artifact(repo_db, encryption_required=encrypted, key=key)
        if encrypted:
            # validate_identity reads the signed SEC-05 manifest and local
            # generation floor, but *does not pin or mutate it*.
            validate_identity(repo_db, key)
        if inspect_runtime_database() is not DatabaseLifecycleState.AVAILABLE:
            return OfflineReadEligibility(False, "Local database integrity check failed.")
        return OfflineReadEligibility(True, "Verified accepted local database is safe for offline READ.")
    except Exception:
        # Cached identity/key failures are intentionally indistinguishable
        # in the UX; detailed exception must remain in local diagnostic logs.
        return OfflineReadEligibility(False, "Local database provenance or integrity is unverified.")
