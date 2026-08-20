# -*- coding: utf-8 -*-
"""
CollaborationPoller - Background poller for remote collaboration state.
Observes remote lock, queue, and version with bounded frequency.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from enum import Enum

from PySide6.QtCore import (
    QObject, QThread, QTimer, Signal, QCoreApplication,
    QMetaObject, Qt, Slot
)

from centermanager.events.event_bus import EventBus
from centermanager.events.event import Event

logger = logging.getLogger(__name__)


class PollerMode(Enum):
    NORMAL = "normal"
    WAITING = "waiting"
    BACKOFF = "backoff"
    STOPPED = "stopped"


@dataclass
class CollaborationSnapshot:
    """Immutable snapshot of remote collaboration state."""
    timestamp: datetime = field(default_factory=datetime.now)
    remote_lock: Dict[str, Any] = field(default_factory=dict)
    queue: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    poll_status: str = "unknown"  # "success", "error"
    error: Optional[str] = None
    is_stale: bool = False

    def is_success(self) -> bool:
        return self.poll_status == "success"

    def has_lock(self) -> bool:
        return self.remote_lock.get("locked", False)

    def lock_owner(self) -> Optional[str]:
        return self.remote_lock.get("owner")

    def lock_session(self) -> Optional[str]:
        return self.remote_lock.get("session_id")

    def queue_length(self) -> int:
        return self.queue.get("length", 0)

    def is_changed_from(self, other: "CollaborationSnapshot") -> bool:
        if other is None:
            return True
        if self.poll_status != other.poll_status:
            return True
        if self.remote_lock != other.remote_lock:
            return True
        if self.queue != other.queue:
            return True
        if self.version != other.version:
            return True
        return False


class CollaborationStateChanged(Event):
    """Event emitted when collaboration state changes."""
    def __init__(self, snapshot: CollaborationSnapshot):
        self.snapshot = snapshot


class CollaborationPoller(QObject):
    """Background poller for remote collaboration state."""

    snapshot_changed = Signal(CollaborationSnapshot)
    # Emitted after every completed poll cycle (success or failure). This is a
    # lifecycle/observability signal, not a remote-state-change signal.
    poll_completed = Signal(object)
    refresh_requested = Signal(object)
    mode_change_requested = Signal(object)
    stop_requested = Signal()

    def __init__(
        self,
        collaboration_manager,
        event_bus: Optional[EventBus] = None,
        normal_interval: int = 10,
        waiting_interval: int = 3,
        max_backoff: int = 120,
        initial_backoff: int = 5,
    ):
        super().__init__()
        self._cm = collaboration_manager
        self._event_bus = event_bus

        self._normal_interval = normal_interval
        self._waiting_interval = waiting_interval
        self._max_backoff = max_backoff
        self._initial_backoff = initial_backoff

        self._mode = PollerMode.NORMAL
        self._running = False
        self._poll_in_progress = False
        self._refresh_pending = False
        self._consecutive_failures = 0
        self._last_snapshot: Optional[CollaborationSnapshot] = None
        self._last_poll_at: Optional[datetime] = None
        self._last_success_at: Optional[datetime] = None
        self._current_backoff = initial_backoff
        self._next_poll_delay = normal_interval

        # Thread and timer - timer will be created in the thread
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._on_thread_started)
        self._timer: Optional[QTimer] = None

        # For stopping
        self._stop_requested = False
        # Production keeps the historical default (initial poll on start), while
        # tests/integrators can disable it to make poll cycles deterministic.
        self._initial_poll_enabled = True

        # Connect signals to slots (queued by default due to different threads)
        self.refresh_requested.connect(self._on_refresh_requested, Qt.QueuedConnection)
        self.mode_change_requested.connect(self._on_mode_change_requested, Qt.QueuedConnection)
        self.stop_requested.connect(self._on_stop_requested, Qt.QueuedConnection)

    def start(self, initial_poll: bool = True) -> None:
        """Start the poller in a background thread."""
        if self._running:
            logger.debug("Poller already running")
            return
        self._running = True
        self._stop_requested = False
        self._initial_poll_enabled = initial_poll
        self._thread.start()
        logger.info("CollaborationPoller started")

    def stop(self) -> None:
        """Stop the poller and release resources.

        Uses cooperative shutdown. No QThread.terminate().
        """
        if not self._running:
            return
        self._running = False
        self._stop_requested = True
        # Use blocking invoke to ensure the stop slot runs before we quit
        QMetaObject.invokeMethod(
            self,
            "_on_stop_requested",
            Qt.ConnectionType.BlockingQueuedConnection
        )
        self._thread.quit()
        if not self._thread.wait(5000):
            # Do NOT terminate. This is a lifecycle bug that must be fixed.
            logger.error("Poller thread did not stop gracefully")
            raise RuntimeError("Poller thread did not stop gracefully")
        logger.info("CollaborationPoller stopped")

    def request_refresh(self, reason: Optional[str] = None) -> None:
        """Request an immediate poll, coalescing if already running."""
        if not self._running or self._stop_requested:
            return
        self.refresh_requested.emit(reason)

    def set_mode(self, mode: PollerMode) -> None:
        """Switch polling mode (NORMAL or WAITING)."""
        if self._running and not self._stop_requested:
            self.mode_change_requested.emit(mode)

    @Slot(object)
    def _on_refresh_requested(self, reason: Optional[str]) -> None:
        """Handle refresh request from main thread (runs in poller thread)."""
        if not self._running or self._stop_requested:
            return
        if self._poll_in_progress:
            self._refresh_pending = True
            logger.debug(f"Refresh requested while poll in progress (reason: {reason})")
        else:
            self._schedule_poll(0)

    @Slot(object)
    def _on_mode_change_requested(self, mode: PollerMode) -> None:
        """Handle mode change from main thread (runs in poller thread)."""
        if self._mode == mode:
            return
        self._mode = mode
        logger.info(f"Poller mode changed to {mode.value}")
        self._update_interval()

    @Slot()
    def _on_stop_requested(self) -> None:
        """Handle stop request from main thread (runs in poller thread)."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
            logger.debug("Timer stopped from poller thread")
        # No need to quit thread here; stop() will call quit() from main thread.

    def _on_thread_started(self) -> None:
        """Called when the background thread starts. Create timer here."""
        if self._stop_requested:
            return
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._poll)
        # Preserve production behavior unless explicitly disabled by the caller.
        if self._initial_poll_enabled:
            self._schedule_poll(0)

    def _schedule_poll(self, delay_seconds: float) -> None:
        """Schedule a poll after delay (in seconds). Must be called from poller thread."""
        if self._stop_requested or self._timer is None or not self._running:
            return
        # Stop any pending timer
        self._timer.stop()
        interval_ms = max(100, int(delay_seconds * 1000))
        self._timer.setInterval(interval_ms)
        self._timer.start()
        logger.debug(f"Next poll scheduled in {delay_seconds:.1f}s")

    def _poll(self) -> None:
        """Perform a single poll cycle. Runs in poller thread."""
        if self._poll_in_progress:
            logger.warning("Poll already in progress, skipping")
            return
        if self._stop_requested:
            logger.debug("Poll skipped due to stop requested")
            return

        self._poll_in_progress = True
        self._refresh_pending = False
        self._last_poll_at = datetime.now()

        try:
            # Observe remote state
            remote_lock = self._cm.get_lock_status()
            queue = self._cm.get_queue()
            # Get version if available
            version = 0
            try:
                version = self._cm.get_version()
            except Exception:
                pass

            snapshot = CollaborationSnapshot(
                timestamp=datetime.now(),
                remote_lock=remote_lock,
                queue=queue,
                version=version,
                poll_status="success",
                error=None,
                is_stale=False,
            )

            # Success
            self._consecutive_failures = 0
            self._current_backoff = self._initial_backoff
            self._last_success_at = datetime.now()

            # Check for changes
            if self._last_snapshot is None or snapshot.is_changed_from(self._last_snapshot):
                self._last_snapshot = snapshot
                self.snapshot_changed.emit(snapshot)
                if self._event_bus:
                    self._event_bus.publish(CollaborationStateChanged(snapshot))
                logger.debug("Snapshot changed and emitted")
            else:
                logger.debug("Snapshot unchanged")

        except Exception as e:
            logger.exception("Poll failed")
            self._consecutive_failures += 1
            # Retain last successful snapshot, but mark as stale/error
            if self._last_snapshot is not None:
                stale_snapshot = CollaborationSnapshot(
                    timestamp=datetime.now(),
                    remote_lock=self._last_snapshot.remote_lock.copy(),
                    queue=self._last_snapshot.queue.copy(),
                    version=self._last_snapshot.version,
                    poll_status="error",
                    error=str(e),
                    is_stale=True,
                )
                if stale_snapshot.is_changed_from(self._last_snapshot):
                    self._last_snapshot = stale_snapshot
                    self.snapshot_changed.emit(stale_snapshot)
                    if self._event_bus:
                        self._event_bus.publish(CollaborationStateChanged(stale_snapshot))
                    logger.debug("Emitted stale snapshot due to poll failure")
            else:
                error_snapshot = CollaborationSnapshot(
                    timestamp=datetime.now(),
                    remote_lock={},
                    queue={},
                    version=0,
                    poll_status="error",
                    error=str(e),
                    is_stale=True,
                )
                self._last_snapshot = error_snapshot
                self.snapshot_changed.emit(error_snapshot)
                if self._event_bus:
                    self._event_bus.publish(CollaborationStateChanged(error_snapshot))

            # Backoff
            self._current_backoff = min(self._current_backoff * 2, self._max_backoff)
            self._schedule_poll(self._current_backoff)

        finally:
            self._poll_in_progress = False
            if self._refresh_pending and not self._stop_requested and self._running:
                self._refresh_pending = False
                logger.debug("Scheduling follow-up poll due to pending refresh")
                self._schedule_poll(0)
            elif not self._stop_requested and self._running:
                # No pending refresh, schedule next normal poll/backoff interval.
                self._update_interval()

            # This signal means a poll cycle actually completed. It must not be
            # confused with snapshot_changed, which is intentionally emitted only
            # when the observable collaboration snapshot changes.
            self.poll_completed.emit({
                "success": self._consecutive_failures == 0,
                "consecutive_failures": self._consecutive_failures,
                "current_backoff": self._current_backoff,
                "last_poll_at": self._last_poll_at,
            })

    def _update_interval(self) -> None:
        """Update polling interval based on mode and failure state.
        Must be called from poller thread.
        """
        if self._consecutive_failures > 0:
            # Already in backoff, do nothing
            return

        if self._mode == PollerMode.WAITING:
            self._next_poll_delay = self._waiting_interval
        else:
            self._next_poll_delay = self._normal_interval

        self._schedule_poll(self._next_poll_delay)
        logger.debug(f"Next poll in {self._next_poll_delay}s (mode={self._mode.value})")

    def get_last_snapshot(self) -> Optional[CollaborationSnapshot]:
        """Get the last known snapshot (may be stale)."""
        return self._last_snapshot

    def get_status(self) -> Dict[str, Any]:
        """Get poller status for diagnostics."""
        return {
            "running": self._running,
            "mode": self._mode.value,
            "poll_in_progress": self._poll_in_progress,
            "refresh_pending": self._refresh_pending,
            "consecutive_failures": self._consecutive_failures,
            "current_backoff": self._current_backoff,
            "next_poll_delay": self._next_poll_delay,
            "last_poll_at": self._last_poll_at.isoformat() if self._last_poll_at else None,
            "last_success_at": self._last_success_at.isoformat() if self._last_success_at else None,
            "has_snapshot": self._last_snapshot is not None,
            "snapshot_stale": self._last_snapshot.is_stale if self._last_snapshot else False,
            "snapshot_lock_owner": self._last_snapshot.lock_owner() if self._last_snapshot else None,
        }