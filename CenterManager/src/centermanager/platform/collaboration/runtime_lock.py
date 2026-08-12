# -*- coding: utf-8 -*-
"""RuntimeLock - Distributed lock for write access."""

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
    """
    
    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._writer = AtomicFileWriter(lock_path)
        self._lock_data: Optional[Dict[str, Any]] = None
        self._lock_acquired = False
    
    def acquire(self, session: RuntimeSession, timeout_seconds: int = 30) -> bool:
        """
        Acquire the lock for a session.
        Returns True if acquired, False if already held by another session.
        Raises LockTimeoutError if timeout exceeded.
        """
        start_time = time.time()
        
        while True:
            # Read current lock state
            current = self._read_lock()
            
            # Check if lock is held
            if current.get("locked", False):
                owner_id = current.get("session_id")
                if owner_id == session.session_id:
                    # Already owned by this session
                    self._lock_acquired = True
                    self._lock_data = current
                    logger.debug(f"Lock already held by session {session.session_id}")
                    return True
                
                # Check if lock has expired (stale)
                last_heartbeat = current.get("last_heartbeat")
                if last_heartbeat:
                    try:
                        hb_time = datetime.fromisoformat(last_heartbeat)
                        if (datetime.now() - hb_time).total_seconds() > 60:
                            # Stale lock - force release
                            logger.warning(f"Force releasing stale lock from {current.get('session_id')}")
                            self._force_release()
                            continue
                    except Exception:
                        pass
                
                # Lock held by someone else - check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    raise LockTimeoutError(
                        f"Lock held by {current.get('session_id')} for {elapsed:.1f}s (timeout {timeout_seconds}s)"
                    )
                
                logger.debug(f"Lock held by {current.get('session_id')}, waiting...")
                time.sleep(0.5)
                continue
            
            # Lock is free - acquire it
            lock_data = {
                "locked": True,
                "session_id": session.session_id,
                "machine_fingerprint": session.machine_fingerprint,
                "user_id": session.user_id,
                "username": session.username,
                "acquired_at": datetime.now().isoformat(),
                "last_heartbeat": datetime.now().isoformat(),
                "runtime_version": session.runtime_version,
            }
            
            self._write_lock(lock_data)
            self._lock_acquired = True
            self._lock_data = lock_data
            logger.info(f"Lock acquired by session {session.session_id} (user: {session.username})")
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
        lock_data = {
            "locked": False,
            "session_id": None,
            "machine_fingerprint": None,
            "user_id": None,
            "username": None,
            "acquired_at": None,
            "last_heartbeat": None,
            "runtime_version": None,
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
            self._write_lock(current)
            self._lock_data = current
            return True
        
        self._lock_acquired = False
        return False
    
    def is_locked(self) -> bool:
        """Check if lock is currently held."""
        current = self._read_lock()
        return current.get("locked", False)
    
    def get_owner(self) -> Optional[str]:
        """Get the session ID of the lock owner."""
        current = self._read_lock()
        return current.get("session_id") if current.get("locked", False) else None
    
    def get_lock_info(self) -> Dict[str, Any]:
        """Get full lock information."""
        return self._read_lock()
    
    def _read_lock(self) -> Dict[str, Any]:
        """Read lock data from file."""
        if not self._lock_path.exists():
            return {
                "locked": False,
                "session_id": None,
                "machine_fingerprint": None,
                "user_id": None,
                "username": None,
                "acquired_at": None,
                "last_heartbeat": None,
                "runtime_version": None,
            }
        try:
            with open(self._lock_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {
                "locked": False,
                "session_id": None,
                "machine_fingerprint": None,
                "user_id": None,
                "username": None,
                "acquired_at": None,
                "last_heartbeat": None,
                "runtime_version": None,
            }
    
    def _write_lock(self, data: Dict[str, Any]) -> None:
        """Write lock data atomically."""
        self._writer.write_json(data)