# -*- coding: utf-8 -*-
"""
LockManager - distributed lock with generation, lease and finishing semantics.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from .lock_repository import LockRepository

logger = logging.getLogger(__name__)


class LockManager:
    def __init__(self, repository: LockRepository, timeout_seconds: int = 60):
        self._repository = repository
        self._timeout_seconds = timeout_seconds

    # ---- Existing methods (unchanged) ----

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
        if not self.is_locked():
            return False
        last_hb = self.get_last_heartbeat()
        if last_hb is None:
            return True
        age = (datetime.now() - last_hb).total_seconds()
        return age > self._timeout_seconds

    def acquire(self, owner: str, session_id: str) -> bool:
        logger.debug(f"Attempting to acquire lock for owner={owner}, session={session_id}")
        lock = self._repository.get_lock()

        if lock.get("locked", False):
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
        # Reset finishing fields on fresh acquire
        lock["lock_generation"] = lock.get("lock_generation", 0) + 1
        lock["lease_revision"] = 0
        lock["finishing_started_at"] = None
        lock["finishing_deadline"] = None
        lock["publish_intent"] = False
        self._repository.save_lock(lock)
        logger.info(f"Lock acquired by {owner}, session {session_id}, generation {lock['lock_generation']}")
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
        # Preserve generation but do not increment; reset finishing
        lock["lease_revision"] = 0
        lock["finishing_started_at"] = None
        lock["finishing_deadline"] = None
        lock["publish_intent"] = False
        self._repository.save_lock(lock)
        logger.info("Lock force-released")

    def recover_stale(self) -> bool:
        if self.is_stale():
            logger.warning("Recovering stale lock")
            self._force_release()
            return True
        return False

    # ---- New finishing-related methods ----

    def get_lock_generation(self) -> int:
        return self._repository.get_lock().get("lock_generation", 0)

    def get_lease_revision(self) -> int:
        return self._repository.get_lock().get("lease_revision", 0)

    def get_finishing_started_at(self) -> Optional[datetime]:
        val = self._repository.get_lock().get("finishing_started_at")
        if val:
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                pass
        return None

    def get_finishing_deadline(self) -> Optional[datetime]:
        val = self._repository.get_lock().get("finishing_deadline")
        if val:
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                pass
        return None

    def get_publish_intent(self) -> bool:
        return self._repository.get_lock().get("publish_intent", False)

    def set_finishing_data(self, started_at: datetime, deadline: datetime, publish_intent: bool = True) -> None:
        lock = self._repository.get_lock()
        lock["finishing_started_at"] = started_at.isoformat()
        lock["finishing_deadline"] = deadline.isoformat()
        lock["publish_intent"] = publish_intent
        # Bump lease_revision to mark renewal
        lock["lease_revision"] = lock.get("lease_revision", 0) + 1
        self._repository.save_lock(lock)
        logger.info(f"Finishing data set: started={started_at}, deadline={deadline}, publish_intent={publish_intent}")

    def clear_finishing_data(self) -> None:
        lock = self._repository.get_lock()
        lock["finishing_started_at"] = None
        lock["finishing_deadline"] = None
        lock["publish_intent"] = False
        self._repository.save_lock(lock)
        logger.info("Finishing data cleared")

    def increment_generation(self) -> int:
        lock = self._repository.get_lock()
        new_gen = lock.get("lock_generation", 0) + 1
        lock["lock_generation"] = new_gen
        self._repository.save_lock(lock)
        logger.info(f"Lock generation incremented to {new_gen}")
        return new_gen

    def is_finishing_active(self) -> bool:
        """True if finishing data exists and deadline not expired."""
        deadline = self.get_finishing_deadline()
        if deadline is None:
            return False
        return datetime.now() < deadline

    def is_finishing_expired(self) -> bool:
        deadline = self.get_finishing_deadline()
        if deadline is None:
            return False
        return datetime.now() >= deadline