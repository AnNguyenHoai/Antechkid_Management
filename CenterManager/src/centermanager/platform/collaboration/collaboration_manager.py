# -*- coding: utf-8 -*-
"""CollaborationManager - Main collaboration coordination service."""

import logging
import uuid
import threading
from enum import Enum
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from pathlib import Path

from centermanager.core.paths import get_paths
from centermanager.events.event_bus import EventBus

from .runtime_session import RuntimeSession
from .runtime_lock import RuntimeLock
from .write_queue import WriteQueue, WriteRequest
from .heartbeat import HeartbeatRepository, HeartbeatManager
from .presence_manager import PresenceManager
from .arbitration import Priority
from .events import (
    SessionStarted,
    SessionEnded,
    WriteRequested,
    WriteGranted,
    WriteReleased,
    QueueUpdated,
    ModeChanged,
)
from .exceptions import (
    CollaborationNotInitializedError,
    LockTimeoutError,
)

logger = logging.getLogger(__name__)


class WriteRequestResult(Enum):
    GRANTED = "granted"
    WAITING = "waiting"
    REJECTED = "rejected"
    ERROR = "error"


class WriteRequestInfo:
    def __init__(self, result: WriteRequestResult, request_id: str = "", position: int = 0, message: str = ""):
        self.result = result
        self.request_id = request_id
        self.position = position
        self.message = message

    @property
    def is_granted(self) -> bool:
        return self.result == WriteRequestResult.GRANTED

    @property
    def is_waiting(self) -> bool:
        return self.result == WriteRequestResult.WAITING


class CollaborationManager:
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
        self._sync_provider = sync_provider
        self._base_dir = self._runtime_root / "collaboration"
        self._collab_dir = self._base_dir
        self._collab_dir.mkdir(parents=True, exist_ok=True)
        self._queue_dir = self._collab_dir / queue_dir_name
        self._queue_dir.mkdir(parents=True, exist_ok=True)
        self._heartbeat_dir = self._runtime_root / "collaboration" / heartbeat_dir_name
        self._heartbeat_dir.mkdir(parents=True, exist_ok=True)
        self._event_bus = event_bus or EventBus()
        self._lock_timeout = lock_timeout
        self._lock = RuntimeLock(self._collab_dir / "lock.json")
        self._queue = WriteQueue(self._queue_dir)
        self._heartbeat_repo = HeartbeatRepository(self._heartbeat_dir)
        self._presence = PresenceManager(
            heartbeat_repo=self._heartbeat_repo,
            runtime_lock=self._lock,
            write_queue=self._queue,
            timeout_seconds=30,
        )
        self._session: Optional[RuntimeSession] = None
        self._heartbeat_manager: Optional[HeartbeatManager] = None
        self._initialized = False
        self._is_writing = False
        self._lock_acquired = False
        self._state_mutex = threading.RLock()
        self._write_handoff_guard: Optional[Callable[[], bool]] = None

    def set_write_handoff_guard(self, guard: Optional[Callable[[], bool]]) -> None:
        self._write_handoff_guard = guard

    def _get_remote_lock_status(self) -> Dict[str, Any]:
        if self._sync_provider is None:
            return {"locked": False, "owner": None, "session_id": None}
        try:
            return self._sync_provider.remote_lock_status()
        except Exception as e:
            logger.warning(f"Failed to get remote lock status: {e}")
            return {"locked": False, "owner": None, "session_id": None, "status": "unknown", "error": str(e)}

    def _build_lock_data(self) -> Dict[str, Any]:
        now = datetime.now()
        return {
            "locked": True,
            "session_id": self._session.session_id,
            "owner": self._session.username,
            "username": self._session.username,
            "user_id": self._session.user_id,
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": self._session.machine_fingerprint,
            "lease_expires_at": (now + timedelta(seconds=self._lock_timeout)).isoformat(),
            "lock_generation": 0,
            "lease_revision": 0,
            "finishing_started_at": None,
            "finishing_deadline": None,
            "publish_intent": False,
        }

    def _is_lease_valid(self, lease_expires_at: Optional[str]) -> bool:
        if not lease_expires_at:
            return False
        try:
            expires = datetime.fromisoformat(lease_expires_at)
            return datetime.now() < expires
        except Exception:
            return False

    def _enqueue_or_return_waiting(self, reason: str, request_id: str) -> WriteRequestInfo:
        existing = self._queue.get_by_session(self._session.session_id)
        if existing:
            position = self._queue.get_position(self._session.session_id)
            return WriteRequestInfo(WriteRequestResult.WAITING, existing.request_id, position, f"Already waiting (position {position})")
        request = WriteRequest(
            request_id=request_id,
            session_id=self._session.session_id,
            user_id=self._session.user_id,
            username=self._session.username,
            role=self._session.role,
            priority=Priority.from_role(self._session.role),
            timestamp=datetime.now(),
            reason=reason,
            status="pending",
        )
        self._queue.enqueue(request)
        position = self._queue.get_position(self._session.session_id)
        self._event_bus.publish(WriteRequested(
            request_id=request_id,
            session_id=self._session.session_id,
            user_id=self._session.user_id,
            username=self._session.username,
            priority=request.priority,
            reason=reason,
            queue_position=position,
        ))
        self._event_bus.publish(QueueUpdated(
            queue_length=self._queue.count(),
            next_writer=self._queue.peek().username if self._queue.peek() else None,
        ))
        return WriteRequestInfo(WriteRequestResult.WAITING, request_id, position, f"Waiting (position {position})")

    def initialize(self, user_id: str, username: str, role: str, runtime_version: int = 0) -> RuntimeSession:
        if self._initialized:
            return self._session
        self._session = RuntimeSession(user_id=user_id, username=username, role=role, runtime_version=runtime_version)
        self._heartbeat_manager = HeartbeatManager(
            repo=self._heartbeat_repo,
            session=self._session,
            interval_seconds=10,
            callback=lambda *_args, **_kwargs: None,
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
        return self._session

    def shutdown(self) -> None:
        if not self._initialized:
            return
        if self._is_writing:
            self._release_write_internal()
        if self._heartbeat_manager:
            self._heartbeat_manager.stop()
        if self._session:
            self._event_bus.publish(SessionEnded(session_id=self._session.session_id, reason="shutdown"))
        self._initialized = False
        self._session = None

    def request_write(self, reason: str = "") -> WriteRequestInfo:
        """Request write access without conflating remote failures with waiting."""
        if not self._initialized:
            raise CollaborationNotInitializedError("Collaboration not initialized")
        if self._is_writing:
            return WriteRequestInfo(WriteRequestResult.GRANTED, message="Already in WRITE mode")
        request_id = str(uuid.uuid4())

        existing = self._queue.get_by_session(self._session.session_id)
        if existing:
            remote_lock = self._get_remote_lock_status() if self._sync_provider is not None else self._lock.get_lock_info()
            if remote_lock.get("status") == "unknown":
                return WriteRequestInfo(WriteRequestResult.ERROR, existing.request_id, message="Unable to determine collaboration lock state")
            locked = remote_lock.get("locked", False)
            if not locked:
                self._queue.cancel(existing.request_id)
            else:
                position = self._queue.get_position(self._session.session_id)
                return WriteRequestInfo(WriteRequestResult.WAITING, existing.request_id, position, f"Waiting (position {position})")

        if self._sync_provider is not None:
            remote_lock = self._get_remote_lock_status()
            if remote_lock.get("status") == "unknown":
                logger.error("Remote lock state is unknown; refusing to enqueue as WAITING")
                return WriteRequestInfo(WriteRequestResult.ERROR, request_id, message="Unable to determine remote collaboration lock state")
            locked = remote_lock.get("locked", False)
            if locked:
                remote_session_id = remote_lock.get("session_id")
                lease_expires_at = remote_lock.get("lease_expires_at")
                if self._is_lease_valid(lease_expires_at):
                    if remote_session_id == self._session.session_id:
                        self._is_writing = True
                        self._lock_acquired = True
                        return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock already held by this session")
                    return self._enqueue_or_return_waiting(reason, request_id)
                logger.warning("Remote lock lease expired; attempting atomic stale-lock reclaim")

            lock_data = self._build_lock_data()
            try:
                acquired = self._sync_provider.acquire_lock(lock_data)
            except Exception as exc:
                logger.exception("Remote lock acquisition raised")
                return WriteRequestInfo(WriteRequestResult.ERROR, request_id, message=f"Lock acquisition failed: {exc}")
            if acquired:
                self._is_writing = True
                self._lock_acquired = True
                self._sync_local_lock()
                self._event_bus.publish(WriteGranted(
                    session_id=self._session.session_id,
                    user_id=self._session.user_id,
                    username=self._session.username,
                    request_id=request_id,
                    queue_position=0,
                ))
                self._event_bus.publish(ModeChanged(mode="WRITE"))
                return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock acquired")

            # Acquisition may have lost a real race. Re-read authoritative state
            # before deciding whether to wait. Never turn a Git/CAS/network error
            # into WAITING when the remote state is actually free/unknown.
            observed = self._get_remote_lock_status()
            if observed.get("status") == "unknown":
                return WriteRequestInfo(WriteRequestResult.ERROR, request_id, message="Lock acquisition failed and remote state is unknown")
            if observed.get("locked", False) and self._is_lease_valid(observed.get("lease_expires_at")):
                return self._enqueue_or_return_waiting(reason, request_id)
            return WriteRequestInfo(WriteRequestResult.ERROR, request_id, message="Unable to acquire remote lock while it is not held by another active session")

        lock_data = self._lock.get_lock_info()
        if lock_data.get("locked", False):
            lock_session_id = lock_data.get("session_id")
            if self._is_lock_stale_local(lock_data):
                self._lock._force_release()
            elif lock_session_id == self._session.session_id:
                self._is_writing = True
                self._lock_acquired = True
                return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock already held by this session")
            else:
                return self._enqueue_or_return_waiting(reason, request_id)
        try:
            acquired = self._lock.acquire(self._session)
        except LockTimeoutError:
            acquired = False
        if acquired:
            self._is_writing = True
            self._lock_acquired = True
            self._event_bus.publish(WriteGranted(session_id=self._session.session_id, user_id=self._session.user_id, username=self._session.username, request_id=request_id, queue_position=0))
            self._event_bus.publish(ModeChanged(mode="WRITE"))
            return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock acquired")
        return WriteRequestInfo(WriteRequestResult.ERROR, request_id, message="Local lock acquisition failed")

    def _is_lock_stale_local(self, lock_data: Dict[str, Any]) -> bool:
        if not lock_data.get("locked", False):
            return True
        last_hb = lock_data.get("last_heartbeat")
        if not last_hb:
            return True
        try:
            return (datetime.now() - datetime.fromisoformat(last_hb)).total_seconds() > self._lock_timeout
        except Exception:
            return True

    def _sync_local_lock(self) -> None:
        if self._sync_provider is None:
            return
        try:
            lock_status = self._sync_provider.remote_lock_status()
            if lock_status.get("status") == "unknown":
                return
            if lock_status.get("locked", False) and lock_status.get("session_id") == self._session.session_id:
                self._lock._write_lock(lock_status)
                self._lock_acquired = True
            else:
                self._lock._force_release()
                self._lock_acquired = False
        except Exception as e:
            logger.warning(f"Failed to sync local lock: {e}")

    def release_write(self) -> bool:
        if not self._initialized or not self._is_writing:
            return False
        with self._state_mutex:
            if self._sync_provider is not None:
                result = self._sync_provider.release_lock(self._session.username)
                self._lock._force_release()
                self._is_writing = False
                self._lock_acquired = False
                self._event_bus.publish(WriteReleased(session_id=self._session.session_id, user_id=self._session.user_id, username=self._session.username))
                self._event_bus.publish(ModeChanged(mode="READ"))
                return result
            self._lock.release(self._session)
            self._is_writing = False
            self._lock_acquired = False
            self._event_bus.publish(WriteReleased(session_id=self._session.session_id, user_id=self._session.user_id, username=self._session.username))
            self._event_bus.publish(ModeChanged(mode="READ"))
            return True

    def get_lock_status(self) -> Dict[str, Any]:
        if self._sync_provider is not None:
            return self._get_remote_lock_status()
        return self._lock.get_lock_info()

    def get_queue(self) -> Dict[str, Any]:
        requests = self._queue.get_requests()
        next_request = self._queue.peek()
        return {
            "length": len(requests),
            "next": next_request.to_dict() if next_request else None,
            "requests": [r.to_dict() for r in requests],
        }

    def get_version(self) -> int:
        return 0

    def is_writing(self) -> bool:
        return self._is_writing

    def get_session(self) -> Optional[RuntimeSession]:
        return self._session

    def refresh_waiting_request(self, request_id: Optional[str] = None) -> bool:
        if not self._initialized or self._session is None:
            return False
        request = self._queue.get_by_session(self._session.session_id)
        if request is None:
            return False
        if request_id and request.request_id != request_id:
            return False
        return self._queue.refresh(request.request_id)

    def has_pending_waiting_request(self, request_id: Optional[str] = None) -> bool:
        if not self._initialized or self._session is None:
            return False
        request = self._queue.get_by_session(self._session.session_id)
        if request is None:
            return False
        return not request_id or request.request_id == request_id

    def grant_existing_waiting_request(self, request_id: Optional[str] = None) -> bool:
        if not self._initialized or self._is_writing or self._session is None:
            return False
        request = self._queue.get_by_session(self._session.session_id)
        if request is None or (request_id and request.request_id != request_id):
            return False
        queue_head = self._queue.peek()
        if queue_head is None or queue_head.request_id != request.request_id:
            return False
        if self._sync_provider is not None:
            remote_lock = self._get_remote_lock_status()
            if remote_lock.get("status") == "unknown":
                return False
            if remote_lock.get("locked", False) and self._is_lease_valid(remote_lock.get("lease_expires_at")):
                return False
            if not self._sync_provider.acquire_lock(self._build_lock_data()):
                return False
            self._is_writing = True
            self._lock_acquired = True
            self._sync_local_lock()
            if self._write_handoff_guard is not None:
                try:
                    if not self._write_handoff_guard():
                        self._sync_provider.release_lock(self._session.username)
                        self._lock._force_release()
                        self._lock_acquired = False
                        self._is_writing = False
                        return False
                except Exception:
                    try:
                        self._sync_provider.release_lock(self._session.username)
                    finally:
                        self._lock._force_release()
                        self._lock_acquired = False
                        self._is_writing = False
                    return False
            self._event_bus.publish(WriteGranted(session_id=self._session.session_id, user_id=self._session.user_id, username=self._session.username, request_id=request.request_id, queue_position=0))
            self._event_bus.publish(ModeChanged(mode="WRITE"))
            self._queue.cancel(request.request_id)
            self._event_bus.publish(QueueUpdated(queue_length=self._queue.count(), next_writer=self._queue.peek().username if self._queue.peek() else None))
            return True
        if self._lock.is_locked() and not self._is_lock_stale_local(self._lock.get_lock_info()):
            return False
        if self._lock.is_locked():
            self._lock._force_release()
        if not self._lock.acquire(self._session):
            return False
        self._is_writing = True
        self._lock_acquired = True
        self._event_bus.publish(WriteGranted(session_id=self._session.session_id, user_id=self._session.user_id, username=self._session.username, request_id=request.request_id, queue_position=0))
        self._event_bus.publish(ModeChanged(mode="WRITE"))
        self._queue.cancel(request.request_id)
        self._event_bus.publish(QueueUpdated(queue_length=self._queue.count(), next_writer=self._queue.peek().username if self._queue.peek() else None))
        return True

    def _release_write_internal(self) -> bool:
        if self._sync_provider:
            result = self._sync_provider.release_lock(self._session.username)
            self._lock._force_release()
            self._lock_acquired = False
            self._is_writing = False
            return result
        self._lock.release(self._session)
        self._lock_acquired = False
        self._is_writing = False
        return True

    def renew_remote_lease(self, force: bool = False) -> bool:
        if not self._initialized:
            return False
        with self._state_mutex:
            if self._sync_provider is None or not self._is_writing or self._session is None:
                return True
            try:
                remote = self._sync_provider.remote_lock_status()
                if remote.get("status") == "unknown":
                    return False
                if not remote.get("locked", False):
                    return False
                if remote.get("session_id") != self._session.session_id:
                    return False
                return self._sync_provider.renew_lock(self._session.username, self._session.session_id)
            except Exception as e:
                logger.warning(f"Remote lease renewal failed: {e}")
                return False
