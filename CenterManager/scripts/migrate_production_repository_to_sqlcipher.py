#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controlled data-preserving SEC-01 migration of authoritative Git DB.

The fenced remote plaintext DB is the migration source. Runtime DB contents are
never used, preventing a fresh/disposable runtime from replacing business data.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

CENTERMANAGER_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CENTERMANAGER_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from centermanager.core.git_locator import locate_git
from centermanager.core.paths import get_paths
from centermanager.database.artifact_identity import (
    identity_manifest_path,
    local_identity_state_path,
    next_identity_document,
    validate_and_pin_identity,
    write_identity_document,
)
from centermanager.database.artifact_security import authoritative_repository_database_path, validate_database_artifact
from centermanager.database.encryption import DatabaseKeyStore, database_encryption_required, is_plaintext_sqlite_file
from centermanager.database.encryption_migration import encrypt_plaintext_database_in_place
from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.services.git_config_service import GitConfigService

CONFIRM = "MIGRATE-AUTHORITATIVE-DATABASE-TO-SQLCIPHER"
OPERATOR = "SEC06-UAT"
DB_RELATIVE_PATH = "database/center.db"
IDENTITY_RELATIVE_PATH = "database/center.db.identity.json"
COMMIT_MESSAGE = "migrate authoritative database to SQLCipher with SEC-05 identity"


def _remote_main(provider: GitSynchronizationProvider, branch: str) -> str:
    output = provider._run_git_command(["ls-remote", "origin", f"refs/heads/{branch}"])
    if not output.strip():
        raise RuntimeError(f"Remote branch does not exist: {branch}")
    return output.split()[0]


def _build_provider():
    paths = get_paths()
    config = GitConfigService().get_config()
    if config is None:
        raise RuntimeError("Git production-data configuration is missing or cannot be decrypted")
    git_executable = locate_git()
    if not git_executable:
        raise RuntimeError("Git executable is unavailable")
    provider = GitSynchronizationProvider(
        repo_path=paths.runtime_root / "repository",
        repository_url=config.repository_url,
        token=config.token,
        username=config.username,
        branch=config.branch,
        email=config.email or "",
        git_executable=str(git_executable),
    )
    if not provider.connect():
        raise RuntimeError("Unable to connect to the local production-data repository")
    return provider, config.branch, paths.runtime_root


def _write_migrated_identity(repo_db: Path, key: bytes) -> tuple[Path, bool]:
    """Sign migrated ciphertext, preserving a valid predecessor identity if present.

    A legacy plaintext authoritative DB may already carry a SEC-05 sidecar from
    an earlier controlled publication/bootstrap. That sidecar is not ambiguous:
    ``next_identity_document`` authenticates it with the workspace key, preserves
    its stable database_id, and increments generation. Malformed or forged
    sidecars still fail closed inside that identity boundary.
    """
    manifest = identity_manifest_path(repo_db)
    had_predecessor = manifest.is_file()
    document = next_identity_document(repo_db, key, repo_db)
    write_identity_document(manifest, document)
    return manifest, had_predecessor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Encrypt existing authoritative plaintext Git DB without replacing its data.")
    parser.add_argument("--apply", action="store_true", help="Perform migration and remote publication.")
    parser.add_argument("--confirm", help=f"Required with --apply: {CONFIRM}")
    args = parser.parse_args(argv)

    os.environ["ANTECHKIDS_DEPLOYMENT_PROFILE"] = "production"
    repo_db = authoritative_repository_database_path()
    print(f"Authoritative DB: {repo_db}")
    print(f"Encryption policy: {'required' if database_encryption_required() else 'NOT REQUIRED'}")

    if not args.apply:
        print("[DRY-RUN] No files changed, no WRITE lock acquired, and nothing was pushed.")
        print("[INFO] Migration source is remote authoritative DB, never the runtime DB.")
        print(f"[NEXT] Re-run with --apply --confirm {CONFIRM}")
        return 0
    if args.confirm != CONFIRM:
        print(f"[ERROR] Refusing migration: --confirm must equal {CONFIRM}")
        return 2
    if not database_encryption_required():
        print("[ERROR] Refusing migration outside encrypted production mode.")
        return 2

    collaboration = None
    provider = None
    result = 1
    try:
        provider, branch, runtime_root = _build_provider()
        collaboration = CollaborationManager(runtime_root=runtime_root, event_bus=EventBus(), sync_provider=provider)
        collaboration.initialize(user_id="sec06-uat", username=OPERATOR, role="admin", runtime_version=0)
        write = collaboration.request_write("SEC-01/06 authoritative plaintext-to-SQLCipher migration")
        if not write.is_granted:
            raise RuntimeError(f"WRITE lock not granted: {write.result.value}: {write.message}")

        expected_main = _remote_main(provider, branch)
        print(f"[OK] WRITE acquired; remote {branch} fenced at {expected_main}")
        provider._run_git_command(["fetch", "origin", branch])
        provider._run_git_command(["reset", "--hard", expected_main])
        if not repo_db.is_file():
            raise RuntimeError(f"Authoritative database is missing at fenced remote MAIN: {repo_db}")
        if not is_plaintext_sqlite_file(repo_db):
            raise RuntimeError(
                "Fenced authoritative DB is not plaintext. This one-time migration is only for the legacy plaintext boundary."
            )

        key = DatabaseKeyStore().load()
        encrypt_plaintext_database_in_place(repo_db, key)
        validate_database_artifact(repo_db, encryption_required=True, key=key)
        print("[OK] Authoritative database encrypted in place; logical source data preserved.")

        manifest, rotated = _write_migrated_identity(repo_db, key)
        if rotated:
            print(f"[OK] Signed SEC-05 identity rotated from authenticated predecessor: {manifest}")
        else:
            print(f"[OK] Signed SEC-05 identity created: {manifest}")

        # Stage only the migration pair. Normal publish() mirrors runtime
        # attachments, which is intentionally excluded from this one-time DB migration.
        provider._run_git_command(["add", "--force", DB_RELATIVE_PATH, IDENTITY_RELATIVE_PATH])
        staged = provider._run_git_command(["diff", "--cached", "--name-only"])
        staged_paths = {line.strip() for line in staged.splitlines() if line.strip()}
        allowed = {DB_RELATIVE_PATH, IDENTITY_RELATIVE_PATH}
        unexpected = staged_paths - allowed
        if unexpected:
            raise RuntimeError(f"Unexpected staged paths; refusing migration commit: {sorted(unexpected)}")
        if staged_paths != allowed:
            raise RuntimeError(f"Migration must stage exactly DB+identity, got: {sorted(staged_paths)}")

        provider._run_git_command(["commit", "-m", f"{OPERATOR}: {COMMIT_MESSAGE}"])
        provider._push_only(expected_remote_commit=expected_main)

        remote_main = _remote_main(provider, branch)
        local_head = provider._run_git_command(["rev-parse", "HEAD"]).strip()
        if remote_main != local_head or remote_main == expected_main:
            raise RuntimeError(f"Remote verification failed: before={expected_main}, remote={remote_main}, local={local_head}")
        provider._run_git_command(["cat-file", "-e", f"{remote_main}:{DB_RELATIVE_PATH}"])
        provider._run_git_command(["cat-file", "-e", f"{remote_main}:{IDENTITY_RELATIVE_PATH}"])

        # A previous local-only SEC-05 bootstrap may have pinned a disposable DB
        # identity. Only after the migrated pair is durably remote-authoritative
        # may this one-time legacy migration replace that local TOFU state.
        pin = local_identity_state_path()
        if pin.exists():
            pin.unlink()
            print("[OK] Replaced pre-migration local identity pin after remote commit succeeded.")
        validate_and_pin_identity(repo_db, key)

        print(f"[OK] Remote {branch} advanced: {expected_main} -> {remote_main}")
        print("[OK] Remote commit contains encrypted DB + signed SEC-05 identity; identity pinned locally.")
        result = 0
    except Exception as exc:
        print(f"[ERROR] Controlled authoritative migration failed: {exc}")
        result = 1
    finally:
        if collaboration is not None:
            try:
                if getattr(collaboration, "_is_writing", False) and not collaboration.release_write():
                    print("[ERROR] WRITE release failed.")
                    result = 1
                collaboration.shutdown()
            except Exception as exc:
                print(f"[ERROR] WRITE cleanup failed: {exc}")
                result = 1
        if provider is not None:
            provider.disconnect()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
