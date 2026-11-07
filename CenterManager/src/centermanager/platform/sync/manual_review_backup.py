"""REC-02: durable evidence-only backup before Git MAIN replaces local bytes.

This is not another workspace or a second source of truth. Every original
database/WAL, attachment, journal and Git file is retained solely for manual
review, never passed to a publisher or to a live SQLAlchemy engine.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid


class ManualBackupError(RuntimeError):
    pass


def preserve_workspace_for_manual_review(journal, *, reason: str) -> Path:
    """Copy and verify every existing protected workspace file before replace.

    The caller must already have stopped the writer. On a partial copy, leave
    all source bytes untouched and refuse MAIN replacement; a later boot can
    retry into another archive. No source file is unlinked or renamed.
    """
    archive_root = Path(journal.root) / "manual-review"
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = archive_root / uuid.uuid4().hex
    destination.mkdir(mode=0o700)
    records = {}
    try:
        # Include original Recovery log/outbox/cases as well as DB/WAL and
        # attachments. Never traverse manual-review itself (it contains this
        # destination and possibly earlier archives).
        roots = dict(journal._workspace_roots())
        roots["recovery"] = journal.root
        for category, location in sorted(roots.items()):
            location = Path(location)
            if not location.exists():
                continue
            if location.is_symlink() or not location.is_dir():
                raise ManualBackupError("Protected workspace root is unsafe.")
            for source in sorted(location.rglob("*")):
                if category == "recovery" and source.is_relative_to(archive_root):
                    continue
                if source.is_symlink():
                    raise ManualBackupError("Symlink in protected workspace; refuse replacement.")
                if not source.is_file():
                    continue
                rel = Path(category) / source.relative_to(location)
                target = destination / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with source.open("rb") as reader, target.open("xb") as writer:
                    for data in iter(lambda: reader.read(1024 * 1024), b""):
                        writer.write(data)
                        digest.update(data)
                    writer.flush()
                    os.fsync(writer.fileno())
                copied = hashlib.sha256(target.read_bytes()).hexdigest()
                original = hashlib.sha256(source.read_bytes()).hexdigest()
                if copied != digest.hexdigest() or copied != original:
                    raise ManualBackupError("Manual Recovery backup checksum mismatch.")
                records[rel.as_posix()] = copied
        if not records:
            raise ManualBackupError("No local artifacts found to preserve.")
        manifest = destination / "manifest.json"
        with manifest.open("x", encoding="utf-8") as writer:
            json.dump({"format": 1, "reason": reason, "files": records}, writer, sort_keys=True)
            writer.flush()
            os.fsync(writer.fileno())
        return destination
    except Exception:
        # The incomplete archive is never accepted as evidence or as MAIN.
        # Keep copies for diagnostics if deletion is not possible.
        raise


def verify_manual_review_backup(archive: Path) -> None:
    archive = Path(archive)
    if archive.is_symlink() or not archive.is_dir():
        raise ManualBackupError("Manual Recovery archive path is unsafe.")
    try:
        document = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
        records = document["files"]
        if document["format"] != 1 or not isinstance(records, dict) or not records:
            raise ValueError("invalid manifest")
        for rel, expected in records.items():
            path = archive / rel
            if (not isinstance(rel, str) or not isinstance(expected, str)
                    or not path.resolve().is_relative_to(archive.resolve())
                    or path.is_symlink() or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
                raise ManualBackupError("Manual Recovery backup verification failed.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ManualBackupError("Manual Recovery backup metadata is incomplete.") from exc
