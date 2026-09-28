#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controlled SEC-06 publication of encrypted DB+identity to remote Git MAIN.

This command is for normal encrypted-to-encrypted publication. It deliberately
refuses to replace a legacy plaintext authoritative database with an unrelated
runtime database; that boundary requires the data-preserving SEC-01 migration.
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
from centermanager.database.artifact_security import (
    authoritative_repository_database_path,
    materialize_runtime_database_to_repository,
    validate_authoritative_repository_database,
)
from centermanager.database.encryption import database_encryption_required, is_plaintext_sqlite_file
from centermanager.database.engine import get_database_path
from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.services.git_config_service import GitConfigService

CONFIRM = "PUBLISH-PRODUCTION-DATABASE-REMOTE"
OPERATOR = "SEC06-UAT"
COMMIT_MESSAGE = "publish encrypted production database"
IDENTITY_RELATIVE_PATH = "database/center.db.identity.json"


def _remote_main(provider: GitSynchronizationProvider, branch: str) -> str:
    output = provider._run_git_command(["ls-remote", "origin", f"refs/heads/{branch}"])
    if not output.strip():
        raise RuntimeError(f"Remote branch does not exist: {branch}")
    return output.split()[0]


def _build_provider():
    paths = get_paths()
    git_config = GitConfigService().get_config()
    if git_config is None:
        raise RuntimeError("Git production-data configuration is missing or cannot be decrypted")
    git_executable = locate_git()
    if not git_executable:
        raise RuntimeError("Git executable is unavailable")
    provider = GitSynchronizationProvider(
        repo_path=paths.runtime_root / "repository",
        repository_url=git_config.repository_url,
        token=git_config.token,
        username=git_config.username,
        branch=git_config.branch,
        email=git_config.email or "",
        git_executable=str(git_executable),
    )
    if not provider.connect():
        raise RuntimeError("Unable to connect to the local production-data repository")
    return provider, git_config.branch, paths.runtime_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish encrypted production DB+SEC-05 identity to remote Git MAIN.")
    parser.add_argument("--apply", action="store_true", help="Perform remote publication.")
    parser.add_argument("--confirm", help=f"Required with --apply: {CONFIRM}")
    args = parser.parse_args(argv)

    os.environ["ANTECHKIDS_DEPLOYMENT_PROFILE"] = "production"
    runtime_db = get_database_path()
    print(f"Runtime DB: {runtime_db}")
    print(f"Encryption: {'required' if database_encryption_required() else 'NOT REQUIRED'}")

    if not args.apply:
        print("[DRY-RUN] No files changed, no WRITE lock acquired, and nothing was pushed.")
        print(f"[NEXT] Re-run with --apply --confirm {CONFIRM}")
        return 0
    if args.confirm != CONFIRM:
        print(f"[ERROR] Refusing remote publication: --confirm must equal {CONFIRM}")
        return 2
    if not database_encryption_required():
        print("[ERROR] Refusing remote publication outside encrypted production mode.")
        return 2
    if not runtime_db.is_file():
        print(f"[ERROR] Runtime database does not exist: {runtime_db}")
        return 2

    collaboration = None
    provider = None
    result = 1
    try:
        provider, branch, runtime_root = _build_provider()
        collaboration = CollaborationManager(runtime_root=runtime_root, event_bus=EventBus(), sync_provider=provider)
        collaboration.initialize(user_id="sec06-uat", username=OPERATOR, role="admin", runtime_version=0)
        write = collaboration.request_write("SEC-06 controlled encrypted DB publication")
        if not write.is_granted:
            raise RuntimeError(f"WRITE lock not granted: {write.result.value}: {write.message}")

        expected_main = _remote_main(provider, branch)
        print(f"[OK] WRITE acquired; remote {branch} fenced at {expected_main}")

        repo_db = authoritative_repository_database_path()
        if repo_db.is_file() and is_plaintext_sqlite_file(repo_db):
            raise RuntimeError(
                "Refusing to replace a plaintext authoritative DB with the runtime DB. "
                "Run the controlled data-preserving SEC-01 remote encryption migration first."
            )

        published = materialize_runtime_database_to_repository()
        validate_authoritative_repository_database()
        identity = published.with_name(published.name + ".identity.json")
        if not identity.is_file():
            raise RuntimeError(f"SEC-05 identity was not created: {identity}")
        provider._run_git_command(["add", "--force", IDENTITY_RELATIVE_PATH])
        print(f"[OK] Local encrypted DB+identity prepared: {published}")

        provider.publish_only(COMMIT_MESSAGE, OPERATOR, expected_main_commit=expected_main)
        remote_main = _remote_main(provider, branch)
        local_head = provider._run_git_command(["rev-parse", "HEAD"]).strip()
        if remote_main != local_head:
            raise RuntimeError(f"Remote verification failed: remote={remote_main}, local={local_head}")
        provider._run_git_command(["cat-file", "-e", f"{remote_main}:{IDENTITY_RELATIVE_PATH}"])
        print(f"[OK] Remote {branch} advanced: {expected_main} -> {remote_main}")
        print("[OK] Remote commit contains the signed SEC-05 identity sidecar.")
        result = 0
    except Exception as exc:
        print(f"[ERROR] Controlled remote publication failed: {exc}")
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
