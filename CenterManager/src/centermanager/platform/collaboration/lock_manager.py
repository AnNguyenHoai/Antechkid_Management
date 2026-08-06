# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional, Dict, Any
import logging

from .lock_repository import LockRepository
from datetime import datetime, timedelta
logger = logging.getLogger(__name__)


class LockManager:
    def __init__(self, repository: LockRepository):
        self._repository = repository

    def is_locked(self) -> bool:
        return self._repository.get_lock().get("locked", False)

    def get_owner(self) -> Optional[str]:
        return self._repository.get_lock().get("owner")

    def acquire(self, owner: str, session_id: str) -> bool:
        logger.debug(f"Attempting to acquire lock for owner={owner}, session={session_id}")
        lock = self._repository.get_lock()
        
        if lock.get("locked", False):
            started_at = lock.get("started_at")
            if started_at:
                try:
                    dt = datetime.fromisoformat(started_at)
                    age = (datetime.now() - dt).total_seconds()
                    # Nếu lock tồn tại quá 600 giây (10 phút), coi là stale
                    if age > 600:
                        logger.warning(f"Stale lock detected (age: {age:.0f}s). Forcing release.")
                        lock["locked"] = False
                        lock["owner"] = None
                        lock["session_id"] = None
                        lock["started_at"] = None
                        self._repository.save_lock(lock)
                    else:
                        logger.warning(f"Lock held by {lock.get('owner')} for {age:.0f}s")
                        return False
                except Exception as e:
                    logger.error(f"Error parsing lock timestamp: {e}")
                    return False
            else:
                # Locked nhưng không có started_at -> không hợp lệ, giải phóng
                logger.warning("Lock has no started_at timestamp. Forcing release.")
                lock["locked"] = False
                lock["owner"] = None
                lock["session_id"] = None
                lock["started_at"] = None
                self._repository.save_lock(lock)

        # Nếu đến được đây, lock đã rảnh hoặc đã được giải phóng, tiến hành acquire
        lock["locked"] = True
        lock["owner"] = owner
        lock["session_id"] = session_id
        lock["started_at"] = datetime.now().isoformat()
        self._repository.save_lock(lock)
        logger.info(f"Lock acquired by {owner}, session {session_id}")
        return True
    def release(self, owner: str) -> bool:
        logger.debug(f"release() called with owner={owner}")
        try:
            lock = self._repository.get_lock()
            logger.debug(f"Current lock data: {lock}")

            if not lock.get("locked", False):
                logger.info("Lock is already released.")
                return True

            current_owner = lock.get("owner")
            if current_owner != owner:
                logger.warning(
                    f"Lock owner mismatch: lock owner='{current_owner}', "
                    f"request owner='{owner}'. Forcing release."
                )

            # Force release
            lock["locked"] = False
            lock["owner"] = None
            lock["session_id"] = None
            lock["started_at"] = None

            logger.debug("Saving lock data after release...")
            self._repository.save_lock(lock)
            logger.info(f"Lock released successfully by {owner}")
            return True

        except Exception as e:
            logger.exception(f"Exception in release() for owner={owner}: {e}")
            return False