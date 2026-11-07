"""REC-02: immutable, independently verified MAIN candidate for safe startup.

A stage is *not* an active runtime and never grants WRITE authority. Importantly,
creating it never deletes/overwrites a local recovery DB, WAL or journal.
Activation must be a separate, crash-tested transaction; callers must not infer
an approved replacement simply because a stage exists.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


class MainStageError(RuntimeError):
    pass


@dataclass(frozen=True)
class MainStage:
    path: Path
    commit_oid: str
    sha256: str


def _copy_durable(source: Path, destination: Path) -> str:
    if not source.is_file() or source.is_symlink():
        raise MainStageError("MAIN artifact missing or a symlink.")
    digest = hashlib.sha256()
    with source.open("rb") as reader, destination.open("xb") as writer:
        while True:
            block = reader.read(1024 * 1024)
            if not block:
                break
            writer.write(block)
            digest.update(block)
        writer.flush()
        os.fsync(writer.fileno())
    return digest.hexdigest()


def stage_exact_main(provider, repository_root: Path, stage_root: Path, *,
                     validate=None) -> MainStage:
    """Stage an already-checked-out exact remote MAIN into a private directory.

    Cannot stage a stale local checkout or a moving remote ref. A stage never
    changes the live database, Recovery Case, Git refs, or WRITE lock.
    """
    import re

    fetched = provider.get_fetched_remote_main_commit()
    local = provider.get_local_main_commit()
    observed = provider.observe_remote_main_commit()
    if (not fetched or not re.fullmatch(r"[a-fA-F0-9]{40,64}", fetched)
            or fetched != local or fetched != observed):
        raise MainStageError("MAIN OID proof failed; no stage was accepted.")

    repo = Path(repository_root)
    stage_root = Path(stage_root)
    source_db = repo / "database" / "center.db"
    source_identity = repo / "database" / "center.db.identity.json"
    source_manifest = repo / "manifest.json"
    if (not source_db.is_file() or not source_identity.is_file()
            or not source_manifest.is_file()):
        raise MainStageError("Signed MAIN database or manifest is missing.")

    stage_root.mkdir(parents=True, exist_ok=True)
    destination = stage_root / ("main-" + uuid.uuid4().hex)
    destination.mkdir(mode=0o700)
    try:
        db_folder = destination / "database"
        db_folder.mkdir()
        db_digest = _copy_durable(source_db, db_folder / "center.db")
        _copy_durable(source_identity, db_folder / "center.db.identity.json")
        _copy_durable(source_manifest, destination / "manifest.json")

        if validate is None:
            from centermanager.database.startup_security import inspect_authoritative_database_for_startup
            result = inspect_authoritative_database_for_startup(db_folder / "center.db")
            if not result.ready:
                raise MainStageError("Staged MAIN failed SQLCipher/identity validation.")
        else:
            validate(db_folder / "center.db")

        # Avoid trusting a stage if source changes between copy and acceptance.
        if hashlib.sha256(source_db.read_bytes()).hexdigest() != db_digest:
            raise MainStageError("MAIN source changed during staging.")
        if (provider.get_local_main_commit() != fetched
                or provider.observe_remote_main_commit() != fetched):
            raise MainStageError("MAIN advanced during staging.")

        receipt = dict(format=1, accepted_main_oid=fetched, center_db_sha256=db_digest)
        tmp = destination / ".receipt.tmp"
        with tmp.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, destination / "accepted-main.json")
        return MainStage(destination, fetched, db_digest)
    except Exception:
        # Stage contains only freshly created copies; never touch originals.
        shutil.rmtree(destination, ignore_errors=True)
        raise
