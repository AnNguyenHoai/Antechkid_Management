"""REC-02: isolated canonical runtime selection without rewriting legacy recovery.

The legacy runtime, DB/WAL/SHM, Git checkout, journal and captures remain at
their original paths. An isolated replacement has its own sibling recovery
journal. Selection is committed only after its Git-MAIN bootstrap/schema
verification succeeds (REC-03); a crash before that leaves previous routing.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


_NAME = re.compile(r"^runtime-main-[a-f0-9]{32}$")
_MARKER = ".centermanager-active-runtime.json"
_CONFIG_FILES = (
    "config.json",
    "database_key.dpapi",
    "authoritative_database_identity.json",
)


class WorkspaceIsolationError(RuntimeError):
    pass


@dataclass(frozen=True)
class IsolatedWorkspace:
    original: Path
    candidate: Path


def _marker_path(project_root: Path) -> Path:
    return Path(project_root) / _MARKER


def _validated_name(name) -> str:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise WorkspaceIsolationError("Active runtime selection contains an invalid workspace name.")
    return name


def read_selected_workspace(project_root: Path) -> tuple[Path | None, tuple[Path, ...]]:
    """Read the pinned selection without changing any workspace."""
    project_root = Path(project_root).resolve()
    marker = _marker_path(project_root)
    if not marker.exists():
        return None, ()
    if marker.is_symlink():
        raise WorkspaceIsolationError("Active runtime selection must not be a symlink.")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        if data["format"] != 1 or not isinstance(data["retained_roots"], list):
            raise ValueError("format mismatch")
        name = _validated_name(data["active_name"])
        historic = tuple(
            project_root / (n if n == "runtime" else _validated_name(n))
            for n in data["retained_roots"]
        )
        if len(set(historic)) != len(historic) or any(p.is_symlink() for p in historic):
            raise ValueError("duplicate or unsafe history")
        active = project_root / name
        if active.is_symlink() or not active.is_dir() or active in historic:
            raise ValueError("missing or conflicting active workspace")
    except (OSError, KeyError, TypeError, ValueError, WorkspaceIsolationError) as exc:
        raise WorkspaceIsolationError("Active runtime selection is unreadable or unsafe.") from exc
    return active, historic


def prepare_isolated_runtime(paths) -> IsolatedWorkspace:
    """Create a separate *unaccepted* runtime and copy only local credentials.

    Never copy the legacy user database, WAL, Recovery case/journal, attachment
    or Git checkout. No path pointer is changed here. A failed candidate is
    retained for diagnostic inspection and is never treated as an accepted MAIN.
    """
    project_root = Path(paths.project_root).resolve()
    original = Path(paths.runtime_root).resolve()
    if original.parent != project_root:
        raise WorkspaceIsolationError("Runtime lies outside the install root.")
    candidate = project_root / ("runtime-main-" + uuid.uuid4().hex)
    candidate.mkdir(mode=0o700)
    try:
        source = original / "Config"
        if source.is_symlink():
            raise WorkspaceIsolationError("Protected configuration directory is a symlink.")
        dest = candidate / "Config"
        dest.mkdir()
        for name in _CONFIG_FILES:
            infile = source / name
            if not infile.exists():
                continue
            if infile.is_symlink() or not infile.is_file():
                raise WorkspaceIsolationError("Protected workstation configuration is invalid.")
            target = dest / name
            with infile.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
                writer.flush()
                os.fsync(writer.fileno())
        return IsolatedWorkspace(original=original, candidate=candidate)
    except Exception:
        # Never delete a candidate that could have been started by another
        # process after a crash; leave incomplete copy for investigation.
        raise


def accept_isolated_runtime(project_root: Path, workspace: IsolatedWorkspace) -> Path:
    """Atomically switch *future starts* only after caller's MAIN proof passes.

    Call only after the alternate bootstrap and Alembic/receipt validation have
    succeeded, before login or any WRITE can be requested.
    """
    root = Path(project_root).resolve()
    candidate = Path(workspace.candidate).resolve()
    prior = Path(workspace.original).resolve()
    if (candidate.parent != root or not _NAME.fullmatch(candidate.name)
            or prior.parent != root or prior == candidate
            or candidate.is_symlink() or not candidate.is_dir()):
        raise WorkspaceIsolationError("Cannot accept unverified runtime routing.")
    # Cross-process selection CAS: a second instance must never silently
    # redirect future launches away from another newly accepted workspace.
    from PySide6.QtCore import QLockFile
    lock = QLockFile(str(root / ".centermanager-active-runtime.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(0):
        raise WorkspaceIsolationError("Another process is committing runtime selection.")
    try:
        previous_active, retained = read_selected_workspace(root)
        if previous_active is not None and previous_active != prior:
            raise WorkspaceIsolationError("Another active runtime was selected concurrently.")
        if previous_active is None and prior.name != "runtime":
            raise WorkspaceIsolationError("Original runtime is not the canonical active selection.")
        history = [p.name for p in retained]
        if prior.name not in history:
            history.append(prior.name)
        receipt = {"format": 1, "active_name": candidate.name, "retained_roots": history}
        marker = _marker_path(root)
        temp = marker.with_name("." + marker.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temp.open("x", encoding="utf-8") as stream:
                json.dump(receipt, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, marker)
        finally:
            temp.unlink(missing_ok=True)
    finally:
        lock.unlock()
    return candidate
