# -*- coding: utf-8 -*-
"""RuntimeLock - Distributed lock for write access with finishing semantics."""

import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from centermanager.platform.repository.atomic_file_writer import AtomicFileWriter
from .exceptions import LockAlreadyHeldError, LockNotHeldError, LockTimeoutError
from .runtime_session import RuntimeSession

logger = logging.getLogger(__name__)


class RuntimeLock:
    """
    Distributed lock stored in collaboration/lock.json.
    Uses AtomicFileWriter for safe writes.
    Extended with finishing semantics: generation, lease, deadline.
    """

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._writer = AtomicFileWriter(lock_path)
        self._lock_data: Optional[Dict[str, Any]] = None
        self._lock_acquired = False

    def _default_lock_data(self) -> Dict[str, Any]:
        return {
            "locked": False,
            "session_id": None,
            "machine_fingerprint": None,
            "user_id": None,
            "username": None,
            "acquired_at": None,
            "last_heartbeat": None,
            "runtime_version": None,
            # Finishing fields
            "lock_generation": 0,
            "lease_revision": 0,
            "finishing_started_at": None,
            "finishing_deadline": None,
            "publish_intent": False,
        }

    def _read_lock(self) -> Dict[str, Any]:
        """Read lock data from file."""
        if not self._lock_path.exists():
            return self._default_lock_data()
        try:
            with open(self._lock_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure all finishing fields exist
            for key, default in self._default_lock_data().items():
                if key not in data:
                    data[key] = default
            return data
        except (json.JSONDecodeError, FileNotFoundError):
            return self._default_lock_data()

    def _write_lock(self, data: Dict[str, Any]) -> None:
        """Write lock data atomically."""
        self._writer.write_json(data)

    # ---- Acquire / Release ----

    def acquire(self, session: RuntimeSession, timeout_seconds: int = 30) -> bool:
        """Acquire the lock for a session."""
        start_time = time.time()

        while True:
            current = self._read_lock()

            if current.get("locked", False):
                owner_id = current.get("session_id")
                if owner_id == session.session_id:
                    self._lock_acquired = True
                    self._lock_data = current
                    logger.debug(f"Lock already held by session {session.session_id}")
                    return True

                # Check stale (using heartbeat)
                last_heartbeat = current.get("last_heartbeat")
                if last_heartbeat:
                    try:
                        hb_time = datetime.fromisoformat(last_heartbeat)
                        if (datetime.now() - hb_time).total_seconds() > 60:
                            logger.warning(f"Force releasing stale lock from {current.get('session_id')}")
                            self._force_release()
                            continue
                    except Exception:
                        pass

                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    raise LockTimeoutError(
                        f"Lock held by {current.get('session_id')} for {elapsed:.1f}s (timeout {timeout_seconds}s)"
                    )

                logger.debug(f"Lock held by {current.get('session_id')}, waiting...")
                time.sleep(0.5)
                continue

            # Lock is free - acquire
            lock_data = {
                "locked": True,
                "session_id": session.session_id,
                "machine_fingerprint": session.machine_fingerprint,
                "user_id": session.user_id,
                "username": session.username,
                "acquired_at": datetime.now().isoformat(),
                "last_heartbeat": datetime.now().isoformat(),
                "runtime_version": session.runtime_version,
                # Reset finishing fields
                "lock_generation": current.get("lock_generation", 0) + 1,
                "lease_revision": 0,
                "finishing_started_at": None,
                "finishing_deadline": None,
                "publish_intent": False,
            }

            self._write_lock(lock_data)
            self._lock_acquired = True
            self._lock_data = lock_data
            logger.info(f"Lock acquired by session {session.session_id} (user: {session.username}), generation {lock_data['lock_generation']}")
            return True

    def release(self, session: RuntimeSession) -> bool:
        """Release the lock if held by this session."""
        if not self._lock_acquired:
            current = self._read_lock()
            if current.get("session_id") == session.session_id:
                self._force_release()
                return True
            raise LockNotHeldError("Lock not held by this session")

        self._force_release()
        self._lock_acquired = False
        self._lock_data = None
        logger.info(f"Lock released by session {session.session_id}")
        return True

    def _force_release(self) -> None:
        """Force release the lock."""
        # Preserve generation but do not increment; reset finishing
        current = self._read_lock()
        lock_data = {
            "locked": False,
            "session_id": None,
            "machine_fingerprint": None,
            "user_id": None,
            "username": None,
            "acquired_at": None,
            "last_heartbeat": None,
            "runtime_version": None,
            "lock_generation": current.get("lock_generation", 0),
            "lease_revision": 0,
            "finishing_started_at": None,
            "finishing_deadline": None,
            "publish_intent": False,
        }
        self._write_lock(lock_data)
        self._lock_acquired = False
        self._lock_data = None
        logger.info("Lock force-released")

    def heartbeat(self, session: RuntimeSession) -> bool:
        """Update heartbeat timestamp for the lock."""
        if not self._lock_acquired:
            current = self._read_lock()
            if current.get("session_id") != session.session_id:
                return False

        current = self._read_lock()
        if current.get("locked", False) and current.get("session_id") == session.session_id:
            current["last_heartbeat"] = datetime.now().isoformat()
            # Bump lease_revision on heartbeat (for lease renewal)
            current["lease_revision"] = current.get("lease_revision", 0) + 1
            self._write_lock(current)
            self._lock_data = current
            return True

        self._lock_acquired = False
        return False

    def is_locked(self) -> bool:
        return self._read_lock().get("locked", False)

    def get_owner(self) -> Optional[str]:
        current = self._read_lock()
        return current.get("session_id") if current.get("locked", False) else None

    def get_lock_info(self) -> Dict[str, Any]:
        return self._read_lock()

    # ---- Finishing methods ----

    def get_lock_generation(self) -> int:
        return self._read_lock().get("lock_generation", 0)

    def get_lease_revision(self) -> int:
        return self._read_lock().get("lease_revision", 0)

    def get_finishing_started_at(self) -> Optional[datetime]:
        val = self._read_lock().get("finishing_started_at")
        if val:
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                pass
        return None

    def get_finishing_deadline(self) -> Optional[datetime]:
        val = self._read_lock().get("finishing_deadline")
        if val:
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                pass
        return None

    def get_publish_intent(self) -> bool:
        return self._read_lock().get("publish_intent", False)

    def set_finishing_data(self, started_at: datetime, deadline: datetime, publish_intent: bool = True) -> None:
        current = self._read_lock()
        current["finishing_started_at"] = started_at.isoformat()
        current["finishing_deadline"] = deadline.isoformat()
        current["publish_intent"] = publish_intent
        current["lease_revision"] = current.get("lease_revision", 0) + 1
        self._write_lock(current)
        self._lock_data = current
        logger.info(f"Finishing data set: started={started_at}, deadline={deadline}, intent={publish_intent}")

    def clear_finishing_data(self) -> None:
        current = self._read_lock()
        current["finishing_started_at"] = None
        current["finishing_deadline"] = None
        current["publish_intent"] = False
        self._write_lock(current)
        self._lock_data = current
        logger.info("Finishing data cleared")

    def increment_generation(self) -> int:
        current = self._read_lock()
        new_gen = current.get("lock_generation", 0) + 1
        current["lock_generation"] = new_gen
        self._write_lock(current)
        self._lock_data = current
        logger.info(f"Lock generation incremented to {new_gen}")
        return new_gen

    def is_finishing_active(self) -> bool:
        deadline = self.get_finishing_deadline()
        if deadline is None:
            return False
        return datetime.now() < deadline

    def is_finishing_expired(self) -> bool:
        deadline = self.get_finishing_deadline()
        if deadline is None:
            return False
        return datetime.now() >= deadline