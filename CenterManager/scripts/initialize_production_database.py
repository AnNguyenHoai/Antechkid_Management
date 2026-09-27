#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a fresh blank SQLCipher production database.

This is a controlled first-run setup helper for the medium-security deployment
model. It never migrates the development database and never rewrites Git history.
Run it only on a fresh production workspace before publishing the encrypted DB to
the private production data repository.
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

from sqlalchemy.orm import sessionmaker

from centermanager.core.paths import get_paths
from centermanager.database.artifact_security import validate_database_artifact
from centermanager.database.encryption import DatabaseKeyStore, is_plaintext_sqlite_file
from centermanager.database.engine import (
    create_production_engine,
    get_database_path,
    initialize_runtime_database,
)
from centermanager.database.migration import upgrade_database_to_head
from centermanager.database.seed import seed_roles_and_permissions


_CONFIRMATION = "CREATE-PRODUCTION-DATABASE"


class ProductionInitializationError(RuntimeError):
    pass


def initialize_blank_production_database() -> Path:
    if os.name != "nt":
        raise ProductionInitializationError(
            "Production database initialization requires Windows DPAPI."
        )

    # The helper is explicitly production even when launched from source.
    os.environ["ANTECHKIDS_DEPLOYMENT_PROFILE"] = "production"

    paths = get_paths()
    paths.ensure_directories()
    db_path = get_database_path()
    key_store = DatabaseKeyStore()

    if db_path.exists():
        raise ProductionInitializationError(
            f"Refusing to overwrite an existing runtime database: {db_path}"
        )
    if key_store.bundle_path.exists():
        raise ProductionInitializationError(
            "A database key bundle already exists. Fresh production initialization "
            "requires an empty runtime; use recovery/provisioning instead."
        )

    created_db = False
    created_key = False
    try:
        initialize_runtime_database()
        created_db = db_path.exists()
        created_key = key_store.bundle_path.exists()

        upgrade_database_to_head()

        engine = create_production_engine(echo=False)
        try:
            SessionLocal = sessionmaker(bind=engine)
            with SessionLocal() as session:
                seed_roles_and_permissions(session)
        finally:
            engine.dispose()

        key = key_store.load()
        validate_database_artifact(db_path, encryption_required=True, key=key)
        if is_plaintext_sqlite_file(db_path):
            raise ProductionInitializationError(
                "Production initialization produced a plaintext SQLite file."
            )
        return db_path
    except Exception:
        # This helper only operates on a workspace proven empty above, so a
        # failed first-run can safely remove artifacts it created.
        if created_db:
            for candidate in (
                db_path,
                Path(str(db_path) + "-wal"),
                Path(str(db_path) + "-shm"),
            ):
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass
        if created_key:
            try:
                key_store.bundle_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a fresh blank SQLCipher production database."
    )
    parser.add_argument("--apply", action="store_true", help="Perform initialization.")
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply: {_CONFIRMATION}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.apply:
        print("[DRY-RUN] No files changed.")
        print("This command creates a NEW blank SQLCipher production DB and DPAPI key.")
        print("It refuses to overwrite an existing DB/key and does not rewrite Git history.")
        print(f"Apply with: --apply --confirm {_CONFIRMATION}")
        return 0
    if args.confirm != _CONFIRMATION:
        print("[ERROR] Exact confirmation is required.", file=sys.stderr)
        return 2
    try:
        path = initialize_blank_production_database()
    except Exception as exc:
        print(f"[ERROR] Production initialization failed: {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Fresh encrypted production database created: {path}")
    print("[OK] Initial admin must change the default password at first login.")
    print("[NEXT] Publish only this encrypted DB to the fresh private production data repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
