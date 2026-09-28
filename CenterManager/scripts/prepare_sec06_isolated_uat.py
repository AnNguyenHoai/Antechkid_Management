#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare a disposable packaged-production workspace for SEC-06 manual UAT.

The helper never mutates the source runtime or the real production data repo.
It copies an existing release package to a new target, creates a fresh SQLCipher
DB + DPAPI key inside that copy, seeds the default admin, creates a signed SEC-05
identity, and publishes a complete authoritative repository to a LOCAL bare Git
repository.

Windows only. The target and local remote must not already exist.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sqlalchemy.orm import sessionmaker

import centermanager.core.paths as paths_module
from centermanager.core.crypto import encrypt_git_config
from centermanager.core.paths import Paths
from centermanager.database.artifact_security import (
    materialize_runtime_database_to_repository,
    validate_authoritative_repository_database,
)
from centermanager.database.encryption import DatabaseKeyStore, is_plaintext_sqlite_file
from centermanager.database.engine import create_production_engine, get_database_path, initialize_runtime_database
from centermanager.database.migration import upgrade_fresh_runtime_database_to_head
from centermanager.database.seed import seed_roles_and_permissions

CONFIRM = "PREPARE-ISOLATED-SEC06-UAT"


class UATPreparationError(RuntimeError):
    pass


def _git(*args: str, cwd: Path) -> None:
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), text=True, capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise UATPreparationError(f"git {' '.join(args)} failed: {detail}")


def _redirect_paths(target: Path) -> None:
    redirected = Paths()
    redirected._project_root = target  # isolated test root; never source runtime
    redirected._runtime_root = target / "runtime"
    paths_module._paths = redirected


def _assert_safe(source: Path, target: Path, remote: Path) -> None:
    source = source.resolve()
    target = target.resolve()
    remote = remote.resolve()
    source_runtime = (ROOT / "runtime").resolve()
    if not source.is_dir() or not (source / "CenterManager.exe").is_file():
        raise UATPreparationError("--package must be an extracted release containing CenterManager.exe")
    if target.exists() or remote.exists():
        raise UATPreparationError("Target workspace and local remote must not already exist")
    if target == ROOT.resolve() or target == source_runtime or remote == source_runtime:
        raise UATPreparationError("Refusing to use the source/production runtime as a UAT target")
    if ROOT.resolve() in target.parents or ROOT.resolve() in remote.parents:
        raise UATPreparationError("Place UAT target/remote outside the CenterManager source tree")


def _write_initial_repository_manifest(repo: Path) -> Path:
    """Create the minimum authoritative manifest expected by publish/version flow."""
    manifest_path = repo / "manifest.json"
    manifest = {
        "runtime_version": 1,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "published_by": "SEC06-UAT",
        "description": "Disposable isolated SEC-06 UAT generation 1",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def prepare(package: Path, target: Path, remote: Path) -> None:
    if os.name != "nt":
        raise UATPreparationError("SEC-06 packaged UAT preparation requires Windows DPAPI")
    package, target, remote = package.resolve(), target.resolve(), remote.resolve()
    _assert_safe(package, target, remote)

    shutil.copytree(package, target)
    # Never inherit release/runtime security state or an old Git working tree.
    for relative in ("runtime/Database", "runtime/repository", "runtime/Config"):
        path = target / relative
        if path.exists():
            shutil.rmtree(path)

    os.environ["ANTECHKIDS_DEPLOYMENT_PROFILE"] = "production"
    os.environ["ANTECHKIDS_FORCE_DATABASE_ENCRYPTION"] = "1"
    _redirect_paths(target)
    paths_module.get_paths().ensure_directories()

    db = get_database_path()
    key_store = DatabaseKeyStore()
    if db.exists() or key_store.bundle_path.exists():
        raise UATPreparationError("Isolated runtime was not empty before initialization")

    initialize_runtime_database()
    upgrade_fresh_runtime_database_to_head()
    engine = create_production_engine(echo=False)
    try:
        Session = sessionmaker(bind=engine)
        with Session() as session:
            seed_roles_and_permissions(session)
    finally:
        engine.dispose()

    if is_plaintext_sqlite_file(db):
        raise UATPreparationError("Fresh UAT database unexpectedly has a plaintext SQLite header")

    repo_db = materialize_runtime_database_to_repository()
    validate_authoritative_repository_database()

    repo = target / "runtime" / "repository"
    manifest = _write_initial_repository_manifest(repo)
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.name", "SEC06 UAT", cwd=repo)
    _git("config", "user.email", "sec06-uat@local.invalid", cwd=repo)
    _git(
        "add",
        "database/center.db",
        "database/center.db.identity.json",
        manifest.name,
        cwd=repo,
    )
    _git("commit", "-m", "SEC06 isolated UAT generation 1", cwd=repo)

    remote.parent.mkdir(parents=True, exist_ok=True)
    _git("init", "--bare", str(remote), cwd=target)
    _git("remote", "add", "origin", remote.as_uri(), cwd=repo)
    _git("push", "-u", "origin", "main", cwd=repo)

    git_config = {
        "repository_url": remote.as_uri(),
        "username": "sec06-uat",
        "token": "local-uat-no-network-credential",
        "branch": "main",
        "email": "sec06-uat@local.invalid",
    }
    config = {
        "application": {"name": "CenterManager", "version": "SEC06-UAT"},
        "git": {"config": encrypt_git_config(json.dumps(git_config))},
    }
    config_path = target / "runtime" / "Config" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    print(f"[OK] Isolated package : {target}")
    print(f"[OK] Local Git remote : {remote}")
    print(f"[OK] SQLCipher DB     : {db}")
    print(f"[OK] DPAPI key        : {key_store.bundle_path}")
    print(f"[OK] SEC-05 pair      : {repo_db} + identity sidecar")
    print(f"[OK] Repo manifest    : {manifest} (runtime_version=1)")
    print("[NEXT] Launch CenterManager.exe from the isolated package.")
    print("[UAT-09] Login with the documented default admin credential; password-change UI MUST appear before normal workspace access.")
    print("[SAFETY] This fixture uses a local file:// Git remote and cannot publish to the production data repository.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare isolated SEC-06 packaged-production UAT fixture")
    parser.add_argument("--package", type=Path, required=True, help="Extracted release package directory")
    parser.add_argument("--target", type=Path, required=True, help="NEW isolated package directory")
    parser.add_argument("--remote", type=Path, required=True, help="NEW local bare Git repository path")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)

    if not args.apply:
        print("[DRY-RUN] No files changed.")
        print("The source package is copied; production runtime/data repository are never modified.")
        print(f"[NEXT] Re-run with --apply --confirm {CONFIRM}")
        return 0
    if args.confirm != CONFIRM:
        print("[ERROR] Exact confirmation is required.", file=sys.stderr)
        return 2
    try:
        prepare(args.package, args.target, args.remote)
    except Exception as exc:
        print(f"[ERROR] SEC-06 isolated UAT preparation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
