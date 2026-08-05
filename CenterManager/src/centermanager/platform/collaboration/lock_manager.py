from datetime import datetime
from typing import Optional, Dict, Any
from .lock_repository import LockRepository

class LockManager:
    def __init__(self, repository: LockRepository):
        self._repository = repository

    def is_locked(self) -> bool:
        return self._repository.get_lock().get("locked", False)

    def get_owner(self) -> Optional[str]:
        return self._repository.get_lock().get("owner")

    def acquire(self, owner: str, session_id: str) -> bool:
        lock = self._repository.get_lock()
        if lock.get("locked", False):
            return False
        lock["locked"] = True
        lock["owner"] = owner
        lock["session_id"] = session_id
        lock["started_at"] = datetime.now().isoformat()
        self._repository.save_lock(lock)
        return True

    def release(self, owner: str) -> bool:
        lock = self._repository.get_lock()
        if not lock.get("locked", False):
            return False
        if lock.get("owner") != owner:
            return False
        lock["locked"] = False
        lock["owner"] = None
        lock["session_id"] = None
        lock["started_at"] = None
        self._repository.save_lock(lock)
        return True