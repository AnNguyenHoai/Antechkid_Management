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
    """Use Windows extended-length filesystem paths for existing evidence.

    Long-path policy/registry flags cannot be assumed on customer workstations.
    The prefix is for local file I/O only, never stored in the signed manifest.
    """
    absolute = os.path.abspath(os.fspath(path))
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _workspace_files(location: Path, category: str, archive_root: Path):
    """Iterate protected files without descending into prior manual archives."""
    top = _native_path(location)
    def _on_error(exc):
        raise ManualBackupError("Cannot enumerate protected workspace evidence") from exc

    for current, directories, files in os.walk(top, topdown=True, onerror=_on_error):
        folder = Path(current)
        safe_directories = []
        for name in sorted(directories):
            child = folder / name
            if category == "recovery" and name == "manual-review" and folder == top:
                continue  # Never archive prior archives or the destination itself.
            if child.is_symlink():
                raise ManualBackupError("Symlink in protected workspace; refuse replacement.")
            safe_directories.append(name)
        directories[:] = safe_directories
        for name in sorted(files):
            source = folder / name
            if source.is_symlink():
                raise ManualBackupError("Symlink in protected workspace; refuse replacement.")
            if source.is_file():
                yield source, Path(category) / source.relative_to(top)


def preserve_workspace_for_manual_review(journal, *, reason: str) -> Path:
    """Preserve all local evidence before Git MAIN replacement.

    Short paths keep the previous readable archive layout. Long paths are
    flattened by *relative-path digest* and indexed in manifest v2, avoiding
    WinError 206 even when prior recovery captures have deeply nested folders.
    No original workspace file is modified or removed.
    """
    archive_root = Path(journal.root) / "manual-review"
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = archive_root / uuid.uuid4().hex
    destination.mkdir(mode=0o700)
    records = {}
    try:
        roots = dict(journal._workspace_roots())
        roots["config"] = journal.runtime / "Config"
        roots["recovery"] = journal.root
        for category, location in sorted(roots.items()):
            location = Path(location)
            if not location.exists():
                continue
            if location.is_symlink() or not location.is_dir():
                raise ManualBackupError("Protected workspace root is unsafe.")
            for source, rel in _workspace_files(location, category, archive_root):
                # Reserve margin under MAX_PATH for destination creation and
                # temporary backups, while supporting unicode names in sources.
                stored_rel = rel
                if os.name == "nt" and len(os.fspath(destination / rel)) > 225:
                    stored_rel = Path("long-paths") / hashlib.sha256(
                        rel.as_posix().encode("utf-8")
                    ).hexdigest()
                target = destination / stored_rel
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with source.open("rb") as reader, target.open("xb") as writer:
                    for data in iter(lambda: reader.read(1024 * 1024), b""):
                        writer.write(data)
                        digest.update(data)
                    writer.flush()
                    os.fsync(writer.fileno())
                copied = _hash_file(target)
                original = _hash_file(source)
                if copied != digest.hexdigest() or copied != original:
                    raise ManualBackupError("Manual Recovery backup checksum mismatch.")
                # Legacy short-path entries stay readable. Flattened paths
                # retain their full original logical names in the manifest.
                records[rel.as_posix()] = (
                    copied if stored_rel == rel else
                    {"sha256": copied, "stored_path": stored_rel.as_posix()}
                )
        if not records:
            raise ManualBackupError("No local artifacts found to preserve.")
        manifest = destination / "manifest.json"
        with manifest.open("x", encoding="utf-8") as writer:
            json.dump(
                {"format": 2, "reason": reason, "files": records},
                writer, sort_keys=True, ensure_ascii=False,
            )
            writer.flush()
            os.fsync(writer.fileno())
        return destination
    except Exception:
        # Incomplete archives are never accepted as evidence or Git MAIN.
        # No original file is removed and replacement is denied by caller.
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
        for logical_path, entry in records.items():
            if isinstance(entry, str):
                expected = entry
                stored = logical_path
            elif document["format"] == 2 and isinstance(entry, dict):
                expected = entry.get("sha256")
                stored = entry.get("stored_path")
            else:
                raise ManualBackupError("Manual Recovery backup manifest entry invalid.")
            if not isinstance(logical_path, str) or not isinstance(stored, str):
                raise ManualBackupError("Manual Recovery backup path invalid.")
            # All stored paths must remain relative and inside this archive.
            relative = Path(stored)
            if (relative.is_absolute() or not relative.parts
                    or any(part in (".", "..") for part in relative.parts)):
                raise ManualBackupError("Manual Recovery backup path unsafe.")
            path = archive / relative
            if (not isinstance(expected, str) or len(expected) != 64
                    or not path.resolve().is_relative_to(archive.resolve())
                    or path.is_symlink() or not path.is_file()
                    or _hash_file(path) != expected):
                raise ManualBackupError("Manual Recovery backup verification failed.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ManualBackupError("Manual Recovery backup metadata is incomplete.") from exc
