# -*- coding: utf-8 -*-
"""WRITE-handoff hardening for RuntimeSyncService.

A queued/first writer must not enter EDITING while Qt widgets still project the
pre-handoff database generation.  This module keeps the existing synchronization
implementation intact and adds two fail-closed barriers:

1. database session refresh failures propagate into the handoff result;
2. after runtime/repository/remote verification succeeds, the visible UI is
   refreshed on the Qt GUI thread before the handoff guard returns success.
"""

import logging
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication

from .runtime_sync_service import RuntimeSyncService as _BaseRuntimeSyncService

logger = logging.getLogger(__name__)


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

        # The barrier intentionally avoids importing MainWindow here.  That
        # would create a platform -> UI import cycle during application startup.
        windows = [
            widget
            for widget in app.topLevelWidgets()
            if hasattr(widget, "central_stack") and hasattr(widget, "student_workspace")
        ]
        if not windows:
            # Before MainWindow exists there is no in-memory UI projection to
            # invalidate.  A user cannot enter editing from that state.
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

                # Refresh the currently visible workspace as well.  This keeps
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
    """RuntimeSyncService with a synchronous pre-EDITING UI refresh barrier."""

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
