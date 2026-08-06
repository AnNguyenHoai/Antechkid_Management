# -*- coding: utf-8 -*-
"""
HeartbeatService - periodically updates lock.json to prevent stale locks.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

from centermanager.platform.collaboration.lock_repository import LockRepository

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatStatus:
    is_running: bool = False
    last_heartbeat: Optional[datetime] = None
    heartbeat_count: int = 0
    owner: Optional[str] = None
    session_id: Optional[str] = None


class HeartbeatService:
    """
    Manages heartbeat updates for the current write session.
    Updates lock.json with last_heartbeat timestamp.
    """

    def __init__(
        self,
        lock_repository: LockRepository,
        interval_seconds: int = 10,
        app_version: str = "0.1.0",
    ):
        self._lock_repository = lock_repository
        self._interval = interval_seconds
        self._app_version = app_version
        self._status = HeartbeatStatus()
        self._timer = None  # Will be set by HeartbeatTimer

    def start(self, owner: str, session_id: str) -> None:
        """Start heartbeat loop for the current owner."""
        if self._status.is_running:
            logger.warning("Heartbeat already running, stopping first.")
            self.stop()

        self._status.is_running = True
        self._status.owner = owner
        self._status.session_id = session_id
        self._status.heartbeat_count = 0
        self._status.last_heartbeat = datetime.now()

        # Update lock immediately
        self._update_lock()
        logger.info(f"Heartbeat started for owner={owner}, session={session_id}")

    def stop(self) -> None:
        """Stop heartbeat loop."""
        if not self._status.is_running:
            return
        self._status.is_running = False
        logger.info(f"Heartbeat stopped for owner={self._status.owner}")

    def update(self) -> None:
        """Perform a single heartbeat update."""
        if not self._status.is_running:
            logger.debug("Heartbeat skipped: not running")
            return
        try:
            self._update_lock()
            self._status.heartbeat_count += 1
            self._status.last_heartbeat = datetime.now()
            logger.debug(f"Heartbeat #{self._status.heartbeat_count} updated")
        except Exception as e:
            logger.exception("Heartbeat update failed")

    def _update_lock(self):
        lock = self._lock_repository.get_lock()
        if not lock.get("locked", False):
            logger.warning("Lock released externally, stopping heartbeat")
            self.stop()
            return
        lock["last_heartbeat"] = datetime.now().isoformat()
        # Increment by 1
        lock["heartbeat_version"] = lock.get("heartbeat_version", 0) + 1
        lock["application_version"] = self._app_version
        self._lock_repository.save_lock(lock)

    def get_status(self) -> HeartbeatStatus:
        """Return current heartbeat status."""
        if self._status.is_running:
            # Refresh last_heartbeat from lock file
            lock = self._lock_repository.get_lock()
            if lock.get("locked", False):
                self._status.last_heartbeat = datetime.fromisoformat(lock.get("last_heartbeat", ""))
        return self._status

    @property
    def is_running(self) -> bool:
        return self._status.is_running