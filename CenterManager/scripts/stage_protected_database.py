# -*- coding: utf-8 -*-
"""Stage encrypted runtime DB + metadata into SEC-02 protected storage.

This is deliberately non-destructive to the current runtime. It copies ciphertext
into ProgramData, fsyncs and validates it with the already-provisioned protected
service key, then stages metadata. ACL enforcement/cutover remains explicit.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import sys
import uuid
from pathlib import Path

from centermanager.core.paths import get_paths
from centermanager.database.artifact_security import validate_database_artifact
from centermanager.database.encryption import DatabaseKeyStore
from centermanager.security.protected_storage import get_protected_storage_layout


class ProtectedDatabaseStagingError(RuntimeError):
    pass


def _is_windows_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _stage_metadata(source: Path, target: Path, *, overwrite: bool) -> None:
    if not source.is_dir():
        raise ProtectedDatabaseStagingError(f"Runtime metadata is missing: {source}")
    if target.exists() and not overwrite:
        raise ProtectedDatabaseStagingError(
            "Protected metadata already exists; use --overwrite only during authorized restaging."
        )
    temp = target.with_name(f".{target.name}.stage-{uuid.uuid4().hex}")
    previous = target.with_name(f".{target.name}.previous-{uuid.uuid4().hex}")
    try:
        shutil.copytree(source, temp)
        if target.exists():
            os.replace(target, previous)
        try:
            os.replace(temp, target)
        except Exception:
            if previous.exists():
                os.replace(previous, target)
            raise
        if previous.exists():
            shutil.rmtree(previous)
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)


def stage_database(*, overwrite: bool = False) -> Path:
    if sys.platform != "win32":
        raise ProtectedDatabaseStagingError("Protected database staging is Windows-only.")
    if not _is_windows_admin():
        raise ProtectedDatabaseStagingError("Administrator privileges are required.")

    paths = get_paths()
    runtime_db = paths.database_dir / "center.db"
    if not runtime_db.is_file():
        raise ProtectedDatabaseStagingError(f"Runtime database is missing: {runtime_db}")

    layout = get_protected_storage_layout()
    protected_db = layout.database_path
    if protected_db.exists() and not overwrite:
        raise ProtectedDatabaseStagingError(
            "Protected database already exists; use --overwrite only during an authorized restaging."
        )

    legacy_key = DatabaseKeyStore().load()
    service_key = DatabaseKeyStore(
        bundle_path=layout.key_bundle_path,
        machine_scope=True,
    ).load()
    if legacy_key != service_key:
        raise ProtectedDatabaseStagingError(
            "Runtime and protected service key bundles do not contain the same workspace key."
        )

    validate_database_artifact(runtime_db, encryption_required=True, key=legacy_key)
    protected_db.parent.mkdir(parents=True, exist_ok=True)
    temp = protected_db.with_name(f".{protected_db.name}.stage-{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(runtime_db, temp)
        with temp.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        validate_database_artifact(temp, encryption_required=True, key=service_key)
        os.replace(temp, protected_db)
        validate_database_artifact(protected_db, encryption_required=True, key=service_key)
    finally:
        temp.unlink(missing_ok=True)

    layout.metadata_dir.parent.mkdir(parents=True, exist_ok=True)
    _stage_metadata(paths.metadata_dir, layout.metadata_dir, overwrite=overwrite)
    return protected_db


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage encrypted center.db + metadata into SEC-02 protected storage."
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        path = stage_database(overwrite=args.overwrite)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Encrypted database and metadata staged and validated: {path}")
    print("[OK] Existing runtime database was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
