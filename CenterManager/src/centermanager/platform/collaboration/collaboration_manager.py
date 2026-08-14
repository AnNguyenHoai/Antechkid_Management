# -*- coding: utf-8 -*-
"""CollaborationManager - Main collaboration coordination service."""

import logging
import uuid
import threading
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from centermanager.core.paths import get_paths
from centermanager.events.event_bus import EventBus

from .runtime_session import RuntimeSession
from .runtime_lock import RuntimeLock
from .write_queue import WriteQueue, WriteRequest
from .heartbeat import HeartbeatRepository, HeartbeatManager
from .presence_manager import PresenceManager
from .arbitration import Priority, Arbitration
from .events import (
    SessionStarted,
    SessionEnded,
    WriteRequested,
    WriteGranted,
    WriteReleased,
    HeartbeatUpdated,
    HeartbeatTimeout,
    QueueUpdated,
    LockReleased,
    ModeChanged,
)
from .exceptions import (
    CollaborationNotInitializedError,
    LockAlreadyHeldError,
    LockNotHeldError,
    LockTimeoutError,
)

logger = logging.getLogger(__name__)


class CollaborationManager:
    """Main collaboration service."""
    
    def __init__(
        self,
        runtime_root: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
        sync_provider: Optional[Any] = None,
        heartbeat_interval: int = 10,
        lock_timeout: int = 60,
        queue_dir_name: str = "queue",
        heartbeat_dir_name: str = "heartbeat",
    ):
        self._runtime_root = runtime_root or get_paths().runtime_root
        self._collab_dir = self._runtime_root / "collaboration"
        self._collab_dir.mkdir(parents=True, exist_ok=True)
        
        self._event_bus = event_bus or EventBus()
        self._lock_timeout = lock_timeout
        
        # Components
        self._lock = RuntimeLock(self._collab_dir / "lock.json")
        self._queue = WriteQueue(self._collab_dir / queue_dir_name)
        self._heartbeat_repo = HeartbeatRepository(self._collab_dir / heartbeat_dir_name)
        
        # Session
        self._session: Optional[RuntimeSession] = None
        self._heartbeat_manager: Optional[HeartbeatManager] = None
        
        # Presence
        self._presence = PresenceManager(
            heartbeat_repo=self._heartbeat_repo,
            runtime_lock=self._lock,
            write_queue=self._queue,
            timeout_seconds=30,
        )
        
        # State
        self._initialized = False
        self._is_writing = False
        self._lock_acquired = False
        
        # Thread safety
        self._state_mutex = threading.RLock()
        
        # Sync provider for Git lock
        self._sync_provider = sync_provider
        
        logger.info(f"CollaborationManager initialized at {self._collab_dir}")
    
    def initialize(self, user_id: str, username: str, role: str, runtime_version: int = 0) -> RuntimeSession:
        """Initialize collaboration with a user session."""
        if self._initialized:
            logger.warning("Collaboration already initialized")
            return self._session
        
        self._session = RuntimeSession(
            user_id=user_id,
            username=username,
            role=role,
            runtime_version=runtime_version,
        )
        
        self._heartbeat_manager = HeartbeatManager(
            repo=self._heartbeat_repo,
            session=self._session,
            interval_seconds=10,
            callback=self._on_heartbeat,
        )
        self._heartbeat_manager.start()
        
        self._initialized = True
        
        self._event_bus.publish(SessionStarted(
            session_id=self._session.session_id,
            user_id=user_id,
            username=username,
            machine_fingerprint=self._session.machine_fingerprint,
            runtime_version=runtime_version,
        ))
        
        logger.info(f"Collaboration initialized for user {username} (session {self._session.session_id})")
        return self._session
    
    def shutdown(self) -> None:
        if not self._initialized:
            return
        if self._is_writing:
            self._release_write_internal()
        if self._heartbeat_manager:
            self._heartbeat_manager.stop()
        if self._session:
            self._event_bus.publish(SessionEnded(
                session_id=self._session.session_id,
                reason="shutdown",
            ))
        self._initialized = False
        self._session = None
        logger.info("Collaboration shutdown complete")
    
    def request_write(self, reason: str = "") -> bool:
        """Request write access."""
        self._ensure_initialized()
        if self._is_writing:
            return True
        
        # Generate request_id
        request_id = str(uuid.uuid4())
        
        # Always publish WriteRequested event
        self._event_bus.publish(WriteRequested(
            request_id=request_id,
            session_id=self._session.session_id,
            user_id=self._session.user_id,
            username=self._session.username,
            priority=Priority.from_role(self._session.role),
            reason=reason,
            queue_position=self._queue.count(),
        ))
        
        # If sync provider available, use Git lock
        if self._sync_provider is not None:
            lock_data = {
                "locked": True,
                "session_id": self._session.session_id,
                "owner": self._session.username,
                "user_id": self._session.user_id,
                "acquired_at": datetime.now().isoformat(),
                "last_heartbeat": datetime.now().isoformat(),
                "machine": self._session.machine_fingerprint,
            }
            with self._state_mutex:
                if self._sync_provider.acquire_lock(lock_data):
                    self._is_writing = True
                    self._lock_acquired = True
                    self._event_bus.publish(WriteGranted(
                        session_id=self._session.session_id,
                        user_id=self._session.user_id,
                        username=self._session.username,
                        request_id=request_id,
                        queue_position=0,
                    ))
                    self._event_bus.publish(ModeChanged(mode="WRITE"))
                    logger.info(f"Write granted to {self._session.username} via Git lock")
                    return True
                else:
                    logger.info(f"Could not acquire Git lock for {self._session.username}")
                    return False
        else:
            # Fallback file lock
            with self._state_mutex:
                try:
                    acquired = self._lock.acquire(self._session)
                    if acquired:
                        self._is_writing = True
                        self._lock_acquired = True
                        self._event_bus.publish(WriteGranted(
                            session_id=self._session.session_id,
                            user_id=self._session.user_id,
                            username=self._session.username,
                            request_id=request_id,
                            queue_position=0,
                        ))
                        self._event_bus.publish(ModeChanged(mode="WRITE"))
                        logger.info(f"Write granted to {self._session.username} via file lock")
                        return True
                except LockTimeoutError:
                    pass
                return False
    
    def release_write(self) -> bool:
        self._ensure_initialized()
        if not self._is_writing:
            logger.warning("Not in write mode")
            return False
        
        with self._state_mutex:
            if self._sync_provider is not None:
                result = self._sync_provider.release_lock(self._session.username)
                if result:
                    self._is_writing = False
                    self._lock_acquired = False
                    self._event_bus.publish(WriteReleased(
                        session_id=self._session.session_id,
                        user_id=self._session.user_id,
                        username=self._session.username,
                    ))
                    self._event_bus.publish(ModeChanged(mode="READ"))
                    logger.info(f"Write released by {self._session.username}")
                    return True
                else:
                    logger.error("Failed to release Git lock")
                    # Still force release local state to avoid stuck
                    self._is_writing = False
                    self._lock_acquired = False
                    self._event_bus.publish(WriteReleased(
                        session_id=self._session.session_id,
                        user_id=self._session.user_id,
                        username=self._session.username,
                    ))
                    self._event_bus.publish(ModeChanged(mode="READ"))
                    return False
            else:
                self._lock.release(self._session)
                self._is_writing = False
                self._lock_acquired = False
                self._event_bus.publish(WriteReleased(
                    session_id=self._session.session_id,
                    user_id=self._session.user_id,
                    username=self._session.username,
                ))
                self._event_bus.publish(ModeChanged(mode="READ"))
                return True
    
    def _release_write_internal(self) -> bool:
        if self._sync_provider:
            return self._sync_provider.release_lock(self._session.username)
        else:
            self._lock.release(self._session)
            return True
    
    def heartbeat(self) -> bool:
        self._ensure_initialized()
        if self._heartbeat_manager:
            self._heartbeat_manager.update()
            self._event_bus.publish(HeartbeatUpdated(
                session_id=self._session.session_id,
                user_id=self._session.user_id,
                username=self._session.username,
            ))
            return True
        return False
    
    def get_presence(self) -> Dict[str, Any]:
        self._ensure_initialized()
        return self._presence.get_summary()
    
    def get_queue(self) -> Dict[str, Any]:
        self._ensure_initialized()
        return {
            "length": self._queue.count(),
            "requests": [r.to_dict() for r in self._queue.get_requests()],
            "next": self._queue.peek().to_dict() if self._queue.peek() else None,
        }
    
    def get_session(self) -> Optional[RuntimeSession]:
        return self._session
    
    def is_initialized(self) -> bool:
        return self._initialized
    
    def is_writing(self) -> bool:
        return self._is_writing
    
    def _on_heartbeat(self, session: RuntimeSession) -> None:
        self._heartbeat_repo.update(session)
    
    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise CollaborationNotInitializedError("Collaboration not initialized. Call initialize() first.")
    
    def get_queue_length(self) -> int:
        return self._queue.count()
    
    def has_writer(self) -> bool:
        return self._is_writing or self._lock.is_locked()
    
    def ensure_write(self) -> bool:
        self._ensure_initialized()
        return self._is_writing
    
    def get_diagnostics(self) -> Dict[str, Any]:
        self._ensure_initialized()
        lock_info = self._lock.get_lock_info() if hasattr(self._lock, 'get_lock_info') else {}
        return {
            "mode": "WRITE" if self._is_writing else "READ",
            "user": self._session.username if self._session else None,
            "session_id": self._session.session_id if self._session else None,
            "lock": {
                "locked": self._lock.is_locked() if hasattr(self._lock, 'is_locked') else False,
                "owner": self._lock.get_owner() if hasattr(self._lock, 'get_owner') else None,
                "session_id": lock_info.get("session_id"),
                "started_at": lock_info.get("acquired_at"),
                "last_heartbeat": lock_info.get("last_heartbeat"),
                "is_stale": False,
            },
            "session": {
                "active": self._is_writing,
                "owner": self._session.username if self._session else None,
                "session_id": self._session.session_id if self._session else None,
            },
            "git": {"state": "disabled" if self._sync_provider is None else "enabled"},
            "heartbeat": {
                "is_running": self._heartbeat_manager is not None,
                "heartbeat_count": 0,
                "last_heartbeat": None,
                "owner": self._session.username if self._session else None,
            },
            "platform_version": 0,
            "deployment_profile": "standalone",
        }
    
    def get_health(self) -> Dict[str, Any]:
        self._ensure_initialized()
        return {
            "status": "HEALTHY",
            "details": {
                "mode": "WRITE" if self._is_writing else "READ",
                "session": self._session.session_id if self._session else None,
                "lock": self._lock.is_locked() if hasattr(self._lock, 'is_locked') else False,
            }
        }
    
    def get_lock_owner(self) -> Optional[str]:
        return self._lock.get_owner() if hasattr(self._lock, 'get_owner') else None
    
    def get_session_id(self) -> Optional[str]:
        return self._session.session_id if self._session else None
    
    def has_changes(self) -> bool:
        return self._is_writing
    
    def is_lock_held_by_current_session(self) -> bool:
        if not self._lock.is_locked():
            return False
        owner = self._lock.get_owner()
        return owner == self._session.session_id if self._session else False
    
    def current_mode(self) -> str:
        self._ensure_initialized()
        return "WRITE" if self._is_writing else "READ"
    
    def get_version(self) -> int:
        self._ensure_initialized()
        return self._lock_timeout
    
    def get_deployment_profile(self) -> str:
        self._ensure_initialized()
        return "Standalone"
    
    def get_waiting_users(self) -> list:
        self._ensure_initialized()
        requests = self._queue.get_requests()
        waiting = []
        for req in requests:
            if not self._heartbeat_repo.is_expired(req.session_id):
                waiting.append({
                    "username": req.username,
                    "priority": req.priority,
                    "request_id": req.request_id,
                    "session_id": req.session_id,
                    "timestamp": req.timestamp,
                })
        return waiting
    
    def is_next_eligible(self) -> bool:
        if not self._initialized or not self._session:
            return False
        next_req = self._queue.peek()
        if not next_req:
            return False
        return next_req.session_id == self._session.session_id