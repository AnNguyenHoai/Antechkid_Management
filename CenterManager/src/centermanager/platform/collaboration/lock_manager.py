# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from .lock_repository import LockRepository

logger = logging.getLogger(__name__)


class LockManager:
    def __init__(self, repository: LockRepository, timeout_seconds: int = 60):
        self._repository = repository
        self._timeout_seconds = timeout_seconds

    def is_locked(self) -> bool:
        return self._repository.get_lock().get("locked", False)

    def get_owner(self) -> Optional[str]:
        return self._repository.get_lock().get("owner")

    def get_session_id(self) -> Optional[str]:
        return self._repository.get_lock().get("session_id")

    def get_last_heartbeat(self) -> Optional[datetime]:
        lock = self._repository.get_lock()
        hb = lock.get("last_heartbeat")
        if hb:
            try:
                return datetime.fromisoformat(hb)
            except ValueError:
                pass
        return None

    def is_stale(self) -> bool:
        """Check if the current lock is stale (heartbeat timeout)."""
        if not self.is_locked():
            return False
        last_hb = self.get_last_heartbeat()
        if last_hb is None:
            # No heartbeat means it's stale (legacy lock)
            return True
        age = (datetime.now() - last_hb).total_seconds()
        return age > self._timeout_seconds

    def acquire(self, owner: str, session_id: str) -> bool:
        logger.debug(f"Attempting to acquire lock for owner={owner}, session={session_id}")
        lock = self._repository.get_lock()

        if lock.get("locked", False):
            # Check stale
            if self.is_stale():
                logger.warning("Stale lock detected, forcing recovery.")
                self._force_release()
            else:
                started_at = lock.get("started_at")
                if started_at:
                    try:
                        dt = datetime.fromisoformat(started_at)
                        age = (datetime.now() - dt).total_seconds()
                        logger.warning(f"Lock held by {lock.get('owner')} for {age:.0f}s")
                    except Exception:
                        pass
                return False

        lock["locked"] = True
        lock["owner"] = owner
        lock["session_id"] = session_id
        lock["started_at"] = datetime.now().isoformat()
        lock["last_heartbeat"] = datetime.now().isoformat()
        lock["heartbeat_version"] = 0
        self._repository.save_lock(lock)
        logger.info(f"Lock acquired by {owner}, session {session_id}")
        return True

    def release(self, owner: str) -> bool:
        lock = self._repository.get_lock()
        if not lock.get("locked", False):
            return True
        current_owner = lock.get("owner")
        if current_owner != owner:
            logger.warning(f"Lock owner mismatch: lock owner='{current_owner}', request owner='{owner}'. Release denied.")
            return False
        self._force_release()
        return True

    def _force_release(self) -> None:
        lock = self._repository.get_lock()
        lock["locked"] = False
        lock["owner"] = None
        lock["session_id"] = None
        lock["started_at"] = None
        lock["last_heartbeat"] = None
        lock["heartbeat_version"] = None
        self._repository.save_lock(lock)
        logger.info("Lock force-released")

    def recover_stale(self) -> bool:
        """Recover stale lock if exists. Returns True if recovered."""
        if self.is_stale():
            logger.warning("Recovering stale lock")
            self._force_release()
            return True
        return False