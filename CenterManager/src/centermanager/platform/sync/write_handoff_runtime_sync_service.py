# -*- coding: utf-8 -*-
"""WRITE-handoff hardening for RuntimeSyncService.

A queued/first writer must not enter EDITING while either the live runtime DB or
Qt widgets still project the pre-handoff generation. This layer closes both
boundaries fail-closed:

1. authoritative repository -> live runtime replacement is maintenance-fenced,
   WAL/SHM-safe, validated, byte-verified, and rollback-safe;
2. database-session refresh failures propagate into the handoff result;
3. after runtime/repository/remote verification succeeds, the visible UI is
   refreshed on the Qt GUI thread before the handoff guard returns success.
"""

import hashlib
import json
import logging
import os
import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication

from centermanager.core.paths import get_paths
from centermanager.database.artifact_security import (
    validate_authoritative_repository_database,
    validate_database_artifact,
)
from centermanager.database.encryption import DatabaseKeyStore, database_encryption_required
from centermanager.database.migration import (
    upgrade_installed_runtime_database_under_maintenance_to_head,
)

from .runtime_sync_service import RuntimeSyncService as _BaseRuntimeSyncService

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_fsync(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as fsrc, destination.open("wb") as fdst:
        shutil.copyfileobj(fsrc, fdst, length=1024 * 1024)
        fdst.flush()
        os.fsync(fdst.fileno())


class _WriteHandoffUiRefreshBarrier(QObject):
    """Synchronously refresh the authoritative UI projection on the GUI thread."""

    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._last_success = True
        self.refresh_requested.connect(
            self._refresh_on_gui_thread,
            Qt.ConnectionType.BlockingQueuedConnection,
        )

    def refresh(self) -> bool:
        app = QApplication.instance()
        if app is None:
            # Service/unit-test usage can legitimately have no Qt application.
            return True

        if QThread.currentThread() == self.thread():
            return self._refresh_authoritative_projection()

        self._last_success = False
        self.refresh_requested.emit()
        return self._last_success

    @Slot()
    def _refresh_on_gui_thread(self) -> None:
        self._last_success = self._refresh_authoritative_projection()

    def _refresh_authoritative_projection(self) -> bool:
        app = QApplication.instance()
        if app is None:
            return True

        # The barrier intentionally avoids importing MainWindow here. That
        # would create a platform -> UI import cycle during application startup.
        windows = [
            widget
            for widget in app.topLevelWidgets()
            if hasattr(widget, "central_stack") and hasattr(widget, "student_workspace")
        ]
        if not windows:
            # Before MainWindow exists there is no in-memory UI projection to
            # invalidate. A user cannot enter editing from that state.
            return True

        try:
            for window in windows:
                student_workspace = window.student_workspace
                refresh = getattr(student_workspace, "refresh", None)
                if callable(refresh):
                    refresh()

                refresh_current = getattr(
                    student_workspace,
                    "refresh_current_student",
                    None,
                )
                if callable(refresh_current):
                    refresh_current()

                # Refresh the currently visible workspace as well. This keeps
                # non-student dashboards from retaining an old generation when
                # WRITE ownership rotates between machines.
                current_widget = window.central_stack.currentWidget()
                if current_widget is not None and current_widget is not student_workspace:
                    current_refresh = getattr(current_widget, "refresh", None)
                    if callable(current_refresh):
                        current_refresh()

            logger.info("WRITE handoff UI projection refreshed from authoritative runtime")
            return True
        except Exception:
            logger.exception("WRITE handoff UI refresh barrier failed")
            return False


class RuntimeSyncService(_BaseRuntimeSyncService):
    """RuntimeSyncService with atomic DB + synchronous pre-EDITING UI barriers."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # RuntimeSyncService is constructed on the GUI thread in app.main(), so
        # this QObject retains GUI-thread affinity even when a poller thread
        # later executes the queued WRITE handoff.
        self._write_handoff_ui_refresh = _WriteHandoffUiRefreshBarrier()

    def _refresh_db_sessions(self) -> None:
        """Refresh DB sessions and propagate failure to the handoff boundary."""
        from centermanager.database.session import refresh_runtime_db

        refresh_runtime_db()
        logger.info("Database sessions refreshed after runtime update")

    def _apply_runtime_update(self) -> bool:
        """Install the Git-authoritative DB into the live runtime atomically.

        The old implementation truncated/re-wrote live ``center.db`` before
        quiescing SQLAlchemy/DBAPI handles. On WAL mode that allowed stale
        ``center.db-wal`` state from the waiting machine to survive the handoff
        and later overwrite the previous writer's committed data.

        This implementation stages and validates the authoritative artifact
        first, then enters the runtime DB maintenance fence *before* touching the
        live database. The old DB and sidecars are preserved for rollback while
        the new DB is installed with ``os.replace``. No stale WAL/SHM file is
        allowed to accompany the new authoritative DB.
        """
        from centermanager.database import session as session_module

        paths = get_paths()
        repo_db = paths.runtime_root / "repository" / "database" / "center.db"
        runtime_db = paths.database_dir / "center.db"
        repo_manifest = paths.runtime_root / "repository" / "manifest.json"
        runtime_manifest = paths.runtime_root / "manifest.json"

        if not repo_db.exists():
            logger.error(
                "Repository database not found; runtime database cannot be considered synchronized"
            )
            return False

        encrypted = database_encryption_required()
        key = DatabaseKeyStore().load() if encrypted else None

        # Security/identity validation occurs before any mutation of the live DB.
        # The repository remains the sole authoritative source for this handoff.
        try:
            validate_authoritative_repository_database()
        except Exception:
            logger.exception("Authoritative repository DB validation failed before runtime install")
            return False

        runtime_db.parent.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        staged_db = runtime_db.with_name(f".{runtime_db.name}.handoff-{token}.tmp")
        staged_manifest = runtime_manifest.with_name(
            f".{runtime_manifest.name}.handoff-{token}.tmp"
        )
        previous_db = runtime_db.with_name(f".{runtime_db.name}.previous-{token}")
        previous_manifest = runtime_manifest.with_name(
            f".{runtime_manifest.name}.previous-{token}"
        )

        sidecars = [
            runtime_db.with_name(runtime_db.name + "-wal"),
            runtime_db.with_name(runtime_db.name + "-shm"),
            runtime_db.with_name(runtime_db.name + "-journal"),
        ]
        previous_sidecars = {
            sidecar: sidecar.with_name(f".{sidecar.name}.previous-{token}")
            for sidecar in sidecars
        }

        db_preserved = False
        manifest_preserved = False
        preserved_sidecars = []
        new_db_installed = False
        new_manifest_installed = False
        sessions_refreshed = False

        try:
            # Stage and fully validate an immutable copy before fencing runtime.
            _copy_fsync(repo_db, staged_db)
            validate_database_artifact(
                staged_db,
                encryption_required=encrypted,
                key=key,
            )
            expected_hash = _sha256(staged_db)

            if repo_manifest.exists():
                _copy_fsync(repo_manifest, staged_manifest)

            # Critical ordering: quiesce FIRST, mutate live DB SECOND.
            session_module.quiesce_runtime_db()
            logger.info("WRITE handoff runtime DB quiesced before authoritative install")

            if runtime_db.exists():
                os.replace(runtime_db, previous_db)
                db_preserved = True

            # Move old WAL/SHM/journal out of the live namespace. They belong to
            # the previous runtime DB and must never be replayed against the new
            # authoritative artifact.
            for sidecar, backup in previous_sidecars.items():
                if sidecar.exists():
                    os.replace(sidecar, backup)
                    preserved_sidecars.append((sidecar, backup))

            os.replace(staged_db, runtime_db)
            new_db_installed = True

            if repo_manifest.exists():
                if runtime_manifest.exists():
                    os.replace(runtime_manifest, previous_manifest)
                    manifest_preserved = True
                os.replace(staged_manifest, runtime_manifest)
                new_manifest_installed = True

            # Byte-level equality proves the live file is exactly the validated
            # Git artifact while the maintenance fence still prevents any DB open.
            installed_hash = _sha256(runtime_db)
            if installed_hash != expected_hash:
                raise RuntimeError(
                    "Authoritative runtime DB hash mismatch after atomic install: "
                    f"expected={expected_hash}, actual={installed_hash}"
                )

            # The repository database is authoritative for data, but it may have
            # been published by an older executable/schema revision.  Startup
            # migration is not sufficient because every WRITE handoff and
            # background pull replaces the live runtime file again.  Upgrade
            # the freshly installed artifact while the maintenance fence is
            # still held and while the previous runtime is still available for
            # rollback.  Only then rebuild normal runtime sessions.
            upgrade_installed_runtime_database_under_maintenance_to_head()
            logger.info(
                "WRITE/pull runtime schema barrier passed after authoritative install"
            )

            self._refresh_db_sessions()
            sessions_refreshed = True
            logger.info(
                "Runtime database atomically updated from authoritative repository: %s",
                runtime_db,
            )

        except Exception:
            logger.exception("Atomic authoritative runtime materialization failed")

            # If refresh failed it re-enters maintenance mode fail-closed. If an
            # earlier step failed, the original quiesce fence is still active.
            try:
                if not session_module.runtime_db_maintenance_active():
                    session_module.quiesce_runtime_db()

                if new_db_installed and runtime_db.exists():
                    runtime_db.unlink(missing_ok=True)
                for sidecar in sidecars:
                    sidecar.unlink(missing_ok=True)

                if db_preserved and previous_db.exists():
                    os.replace(previous_db, runtime_db)
                for sidecar, backup in preserved_sidecars:
                    if backup.exists():
                        os.replace(backup, sidecar)

                if new_manifest_installed and runtime_manifest.exists():
                    runtime_manifest.unlink(missing_ok=True)
                if manifest_preserved and previous_manifest.exists():
                    os.replace(previous_manifest, runtime_manifest)

                # Restore normal read access to the previous known runtime only
                # after rollback is complete. Handoff still returns False, so the
                # just-acquired WRITE lease will be released by collaboration.
                self._refresh_db_sessions()
                logger.warning("Previous runtime DB restored after failed handoff install")
            except Exception:
                logger.exception(
                    "Runtime rollback failed; maintenance fence remains fail-closed"
                )
            finally:
                staged_db.unlink(missing_ok=True)
                staged_manifest.unlink(missing_ok=True)
            return False

        finally:
            staged_db.unlink(missing_ok=True)
            staged_manifest.unlink(missing_ok=True)

        # Installation succeeded and the new runtime session factory is live.
        # Old DB/WAL artifacts can now be destroyed; they must never be reused.
        previous_db.unlink(missing_ok=True)
        previous_manifest.unlink(missing_ok=True)
        for _, backup in preserved_sidecars:
            backup.unlink(missing_ok=True)

        # Preserve existing metadata-version behavior, but do it only after the
        # authoritative DB has been installed and runtime sessions rebuilt.
        if repo_manifest.exists():
            try:
                with repo_manifest.open("r", encoding="utf-8") as handle:
                    manifest_data = json.load(handle)
                runtime_version = manifest_data.get("runtime_version")
                if runtime_version is not None:
                    meta_version_path = paths.metadata_dir / "version.json"
                    meta_version_path.parent.mkdir(parents=True, exist_ok=True)
                    if meta_version_path.exists():
                        with meta_version_path.open("r", encoding="utf-8") as handle:
                            meta_data = json.load(handle)
                    else:
                        meta_data = {}
                    meta_data["platform_version"] = runtime_version
                    meta_data.pop("pending_version", None)
                    meta_tmp = meta_version_path.with_name(
                        f".{meta_version_path.name}.handoff-{uuid.uuid4().hex}.tmp"
                    )
                    try:
                        with meta_tmp.open("w", encoding="utf-8") as handle:
                            json.dump(meta_data, handle, indent=2, ensure_ascii=False)
                            handle.flush()
                            os.fsync(handle.fileno())
                        os.replace(meta_tmp, meta_version_path)
                    finally:
                        meta_tmp.unlink(missing_ok=True)
                    logger.info(
                        "Metadata version.json updated to platform_version=%s",
                        runtime_version,
                    )
            except Exception:
                logger.exception(
                    "Authoritative DB installed but runtime metadata version update failed"
                )
                return False

        if not sessions_refreshed:
            logger.error("Runtime materialization finished without refreshed DB sessions")
            return False
        return True

    def execute_write_handoff_sync(self) -> bool:
        """Require authoritative runtime *and* UI projection before WRITE grant."""
        if not super().execute_write_handoff_sync():
            return False

        if not self._write_handoff_ui_refresh.refresh():
            logger.error(
                "Write handoff refused: authoritative UI projection could not be refreshed"
            )
            return False

        logger.info("Write handoff runtime/UI refresh barrier completed")
        return True
