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


def _native_path(path: Path) -> Path:
    """Use Windows extended-length paths for copy/verification only.

    The on-disk archive stays in its original location. No global Windows
    long-path setting or administrator rights are required.
    """
    path = Path(path)
    if os.name != "nt":
        return path
    absolute = str(path.resolve())
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _backup_storage_relative(destination: Path, original_relative: Path) -> Path:
    """Keep ordinary paths human-readable; flatten paths unsafe on Windows.

    Archiving adds the recovery root, UUID and category to the original path.
    A path valid in the live repo can exceed Windows MAX_PATH after copying.
    The SHA256 key is based on the *logical* original path (not file contents),
    so files with the same basename remain distinct and auditable.
    """
    candidate = destination / original_relative
    if len(str(candidate)) < 220:
        return original_relative
    identity = hashlib.sha256(original_relative.as_posix().encode("utf-8")).hexdigest()
    return Path("_longpaths") / identity[:2] / identity


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
    relocated = {}
    try:
        # Include original Recovery log/outbox/cases as well as DB/WAL and
        # attachments. Never traverse manual-review itself (it contains this
        # destination and possibly earlier archives).
        roots = dict(journal._workspace_roots())
        # Include machine-bound DPAPI/config evidence when it exists, so
        # workstation reprovisioning cannot destroy the only usable legacy key.
        roots["config"] = journal.runtime / "Config"
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
                storage_rel = _backup_storage_relative(destination, rel)
                target = destination / storage_rel
                _native_path(target.parent).mkdir(parents=True, exist_ok=True)
                if storage_rel != rel:
                    relocated[rel.as_posix()] = storage_rel.as_posix()
                digest = hashlib.sha256()
                with _native_path(source).open("rb") as reader, _native_path(target).open("xb") as writer:
                    for data in iter(lambda: reader.read(1024 * 1024), b""):
                        writer.write(data)
                        digest.update(data)
                    writer.flush()
                    os.fsync(writer.fileno())
                copied = hashlib.sha256(_native_path(target).read_bytes()).hexdigest()
                original = hashlib.sha256(_native_path(source).read_bytes()).hexdigest()
                if copied != digest.hexdigest() or copied != original:
                    raise ManualBackupError("Manual Recovery backup checksum mismatch.")
                records[rel.as_posix()] = copied
        if not records:
            raise ManualBackupError("No local artifacts found to preserve.")
        manifest = destination / "manifest.json"
        with manifest.open("x", encoding="utf-8") as writer:
            json.dump({"format": 2, "reason": reason, "files": records,
                       "relocated": relocated}, writer, sort_keys=True)
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
        if document["format"] not in (1, 2) or not isinstance(records, dict) or not records:
            raise ValueError("invalid manifest")
        relocated = document.get("relocated", {}) if document["format"] == 2 else {}
        if not isinstance(relocated, dict) or not set(relocated).issubset(records):
            raise ValueError("invalid relocation map")
        for rel, expected in records.items():
            stored_rel = relocated.get(rel, rel)
            if (not isinstance(rel, str) or not isinstance(expected, str)
                    or not isinstance(stored_rel, str)
                    or Path(rel).is_absolute() or Path(stored_rel).is_absolute()
                    or ".." in Path(rel).parts or ".." in Path(stored_rel).parts):
                raise ManualBackupError("Manual Recovery backup verification failed.")
            path = archive / stored_rel
            if (not path.resolve().is_relative_to(archive.resolve())
                    or _native_path(path).is_symlink()
                    or not _native_path(path).is_file()
                    or hashlib.sha256(_native_path(path).read_bytes()).hexdigest() != expected):
                raise ManualBackupError("Manual Recovery backup verification failed.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ManualBackupError("Manual Recovery backup metadata is incomplete.") from exc
