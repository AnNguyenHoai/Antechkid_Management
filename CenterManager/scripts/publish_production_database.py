#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controlled publication of the encrypted runtime DB to the authoritative repository.

This command exists for production bootstrap/UAT and operational recovery. It
never copies identity metadata by hand: the security boundary in
``materialize_runtime_database_to_repository`` creates/advances the signed
SEC-05 identity and atomically installs the DB+identity pair.
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

from centermanager.database.artifact_identity import identity_manifest_path
from centermanager.database.artifact_security import (
    authoritative_repository_database_path,
    materialize_runtime_database_to_repository,
    validate_authoritative_repository_database,
)
from centermanager.database.encryption import database_encryption_required
from centermanager.database.engine import get_database_path

CONFIRM = "PUBLISH-PRODUCTION-DATABASE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish the validated production runtime DB to the authoritative repository."
    )
    parser.add_argument("--apply", action="store_true", help="Perform publication.")
    parser.add_argument(
        "--confirm",
        help=f"Required with --apply: {CONFIRM}",
    )
    args = parser.parse_args(argv)

    os.environ["ANTECHKIDS_DEPLOYMENT_PROFILE"] = "production"
    runtime_db = get_database_path()
    repo_db = authoritative_repository_database_path()
    manifest = identity_manifest_path(repo_db)

    print(f"Runtime DB:       {runtime_db}")
    print(f"Authoritative DB: {repo_db}")
    print(f"Identity:         {manifest}")
    print(f"Encryption:       {'required' if database_encryption_required() else 'NOT REQUIRED'}")

    if not args.apply:
        print("[DRY-RUN] No files changed.")
        print(f"[NEXT] Re-run with --apply --confirm {CONFIRM}")
        return 0
    if args.confirm != CONFIRM:
        print(f"[ERROR] Refusing publication: --confirm must equal {CONFIRM}")
        return 2
    if not database_encryption_required():
        print("[ERROR] Refusing controlled production publication outside encrypted production mode.")
        return 2
    if not runtime_db.is_file():
        print(f"[ERROR] Runtime database does not exist: {runtime_db}")
        return 2

    try:
        published = materialize_runtime_database_to_repository()
        validate_authoritative_repository_database()
    except Exception as exc:
        print(f"[ERROR] Production database publication failed: {exc}")
        return 1

    print(f"[OK] Published encrypted authoritative database: {published}")
    print(f"[OK] Signed SEC-05 identity: {identity_manifest_path(published)}")
    print("[OK] Authoritative database and identity validated after publication.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
