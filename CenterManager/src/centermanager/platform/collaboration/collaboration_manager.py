# -*- coding: utf-8 -*-
"""CollaborationManager - Main collaboration coordination service."""

import logging
import uuid
import threading
import json
from enum import Enum
from typing import Optional, Dict, Any, List, Union, Callable
from datetime import datetime, timedelta
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

        # Always place collaboration runtime files OUTSIDE the Git repository
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

        self._initialized = False
        self._is_writing = False
        self._lock_acquired = False
        self._lease_renewal_suspended = False
        self._state_mutex = threading.RLock()
        self._write_handoff_guard: Optional[Callable[[], bool]] = None

        logger.info(f"CollaborationManager initialized at {self._collab_dir}")

    def set_write_handoff_guard(self, guard: Optional[Callable[[], bool]]) -> None:
        """Set synchronous runtime-sync guard for queued write handoff."""
        self._write_handoff_guard = guard

    # ===================== Helper methods =====================

    def _get_remote_lock_status(self) -> Dict[str, Any]:
        """Get authoritative remote lock status."""
        if self._sync_provider is None:
            return {"locked": False, "owner": None, "session_id": None}
        try:
            return self._sync_provider.remote_lock_status()
        except Exception as e:
            logger.warning(f"Failed to get remote lock status: {e}")
            return {"locked": False, "owner": None, "session_id": None}

    def _remote_queue_supported(self) -> bool:
        return bool(
            self._sync_provider is not None
            and hasattr(self._sync_provider, "remote_queue_status")
        )

    def _queue_snapshot(self) -> Dict[str, Any]:
        if self._remote_queue_supported():
            return self._sync_provider.remote_queue_status()
        requests = self._queue.get_requests()
        return {
            "length": len(requests),
            "requests": [request.to_dict() for request in requests],
            "next": requests[0].to_dict() if requests else None,
        }

    def _queue_requests(self) -> List[WriteRequest]:
        snapshot = self._queue_snapshot()
        result = []
        for item in snapshot.get("requests") or []:
            try:
                result.append(WriteRequest.from_dict(item))
            except Exception:
                logger.warning("Ignoring invalid WRITE queue request: %r", item)
        return result

    def _queue_get_by_session(self, session_id: str) -> Optional[WriteRequest]:
        for request in self._queue_requests():
            if request.session_id == session_id:
                return request
        return None

    def _queue_peek(self) -> Optional[WriteRequest]:
        requests = self._queue_requests()
        return requests[0] if requests else None

    def _queue_position(self, session_id: str) -> int:
        for index, request in enumerate(self._queue_requests(), start=1):
            if request.session_id == session_id:
                return index
        return 0

    def _queue_count(self) -> int:
        return len(self._queue_requests())

    def _queue_enqueue(self, request: WriteRequest) -> bool:
        if self._remote_queue_supported():
            return bool(
                self._sync_provider.enqueue_remote_write_request(
                    request.to_dict()
                )
            )
        self._queue.enqueue(request)
        return True

    def _queue_refresh(self, request: WriteRequest) -> bool:
        if self._remote_queue_supported():
            return bool(
                self._sync_provider.refresh_remote_write_request(
                    request.request_id,
                    request.session_id,
                )
            )
        return self._queue.refresh(request.request_id)

    def _queue_cancel(self, request: WriteRequest) -> bool:
        if self._remote_queue_supported():
            return bool(
                self._sync_provider.cancel_remote_write_request(
                    request.request_id,
                    request.session_id,
                )
            )
        return self._queue.cancel(request.request_id)

    def _build_lock_data(self) -> Dict[str, Any]:
        """Build lock data for acquisition."""
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
        """Check if a remote lease is still valid."""
        if not lease_expires_at:
            return False
        try:
            expires = datetime.fromisoformat(lease_expires_at)
            return datetime.now() < expires
        except Exception:
            return False

    def _is_lock_stale(self, lock_data: Dict[str, Any]) -> bool:
        """
        Check if a lock is stale.

        REMOTE MODE (sync_provider is not None):
            SOLE AUTHORITY: lease_expires_at
            Missing lease_expires_at → stale/invalid

        LOCAL MODE (sync_provider is None):
            AUTHORITY: last_heartbeat (unless FINISHING mode with valid deadline)
            Uses local heartbeat timeout, but FINISHING mode overrides.
        """
        if not lock_data.get("locked", False):
            return True

        if self._sync_provider is not None:
            lease_expires_at = lock_data.get("lease_expires_at")
            if not lease_expires_at:
                logger.debug("Remote lock missing lease_expires_at → treating as stale")
                return True
            try:
                expires = datetime.fromisoformat(lease_expires_at)
                is_stale = datetime.now() >= expires
                if is_stale:
                    logger.debug(f"Remote lock lease expired at {expires}")
                return is_stale
            except Exception as e:
                logger.warning(f"Failed to parse lease_expires_at: {e}")
                return True

        finishing_deadline = lock_data.get("finishing_deadline")
        if finishing_deadline:
            try:
                deadline = datetime.fromisoformat(finishing_deadline)
                if datetime.now() < deadline:
                    return False
            except Exception:
                pass

        last_hb = lock_data.get("last_heartbeat")
        if last_hb:
            try:
                hb_time = datetime.fromisoformat(last_hb)
                age = (datetime.now() - hb_time).total_seconds()
                is_stale = age > self._lock_timeout
                if is_stale:
                    logger.debug(f"Local lock heartbeat stale: age={age:.0f}s > timeout={self._lock_timeout}s")
                return is_stale
            except Exception as e:
                logger.warning(f"Failed to parse last_heartbeat: {e}")
                return True

        return True

    def _force_release_lock(self) -> None:
        """Force release the lock (admin/cleanup only)."""
        try:
            if self._sync_provider is not None:
                self._sync_provider.force_release(self._session.username if self._session else "force_release")
                self._lock._force_release()
                self._lock_acquired = False
                self._is_writing = False
            else:
                self._lock._force_release()
                self._lock_acquired = False
                self._is_writing = False
            logger.info("Lock force-released")
        except Exception as e:
            logger.exception(f"Force release lock failed: {e}")

    def _sync_local_lock(self) -> None:
        """Sync local lock file with remote state."""
        if self._sync_provider is None:
            return
        try:
            lock_status = self._sync_provider.remote_lock_status()
            if lock_status.get("locked", False):
                remote_session_id = lock_status.get("session_id")
                if remote_session_id == self._session.session_id:
                    lock_data = {
                        "locked": True,
                        "session_id": lock_status.get("session_id"),
                        "owner": lock_status.get("owner"),
                        "username": lock_status.get("username"),
                        "user_id": lock_status.get("user_id"),
                        "acquired_at": lock_status.get("acquired_at"),
                        "last_heartbeat": datetime.now().isoformat(),
                        "machine": lock_status.get("machine"),
                        "lease_expires_at": lock_status.get("lease_expires_at"),
                        "lock_generation": lock_status.get("lock_generation", 0),
                        "lease_revision": lock_status.get("lease_revision", 0),
                        "finishing_started_at": lock_status.get("finishing_started_at"),
                        "finishing_deadline": lock_status.get("finishing_deadline"),
                        "publish_intent": lock_status.get("publish_intent", False),
                    }
                    self._lock._write_lock(lock_data)
                    self._lock_acquired = True
                    self._is_writing = True
                    logger.info(f"Local lock synced with remote: owner={lock_status.get('owner')}")
                else:
                    self._lock._force_release()
                    self._lock_acquired = False
                    self._is_writing = False
                    logger.info(f"Remote lock held by {lock_status.get('owner')}")
            else:
                self._lock._force_release()
                self._lock_acquired = False
                self._is_writing = False
        except Exception as e:
            logger.warning(f"Failed to sync local lock: {e}")

    def _enqueue_or_return_waiting(self, reason: str, request_id: str) -> WriteRequestInfo:
        try:
            existing = self._queue_get_by_session(self._session.session_id)
            if existing:
                position = self._queue_position(self._session.session_id)
                logger.info(
                    "Session %s already waiting (pos=%s)",
                    self._session.username,
                    position,
                )
                return WriteRequestInfo(
                    WriteRequestResult.WAITING,
                    existing.request_id,
                    position,
                    f"Already waiting (position {position})",
                )

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
            if not self._queue_enqueue(request):
                logger.error(
                    "Shared WRITE queue rejected request %s for %s",
                    request_id,
                    self._session.username,
                )
                return WriteRequestInfo(
                    WriteRequestResult.ERROR,
                    request_id,
                    0,
                    "Unable to join the shared editing queue. Please check connectivity and try again.",
                )

            # Read-after-write acknowledgement: WAITING is only authoritative
            # after this exact request can be observed in the shared queue.
            confirmed = self._queue_get_by_session(self._session.session_id)
            if confirmed is None or confirmed.request_id != request_id:
                logger.error(
                    "Shared WRITE queue could not confirm request %s for %s",
                    request_id,
                    self._session.username,
                )
                try:
                    self._queue_cancel(request)
                except Exception:
                    logger.warning(
                        "Unable to clean up unconfirmed WRITE request %s",
                        request_id,
                        exc_info=True,
                    )
                return WriteRequestInfo(
                    WriteRequestResult.ERROR,
                    request_id,
                    0,
                    "Editing request could not be confirmed in the shared queue. Please try again.",
                )

            position = self._queue_position(self._session.session_id)
            if position <= 0:
                logger.error(
                    "Confirmed WRITE request %s has no valid queue position",
                    request_id,
                )
                return WriteRequestInfo(
                    WriteRequestResult.ERROR,
                    request_id,
                    0,
                    "Editing request was not assigned a valid queue position. Please try again.",
                )

            self._event_bus.publish(WriteRequested(
                request_id=request_id,
                session_id=self._session.session_id,
                user_id=self._session.user_id,
                username=self._session.username,
                priority=request.priority,
                reason=reason,
                queue_position=position,
            ))
            try:
                queue_snapshot = self._queue_snapshot()
                next_request = queue_snapshot.get("next") or {}
                self._event_bus.publish(QueueUpdated(
                    queue_length=int(queue_snapshot.get("length", 0) or 0),
                    next_writer=next_request.get("username"),
                ))
            except Exception:
                # The request itself is already authoritatively confirmed.
                # A later observer refresh failure must not turn WAITING into
                # an ERROR or orphan an otherwise valid request.
                logger.debug(
                    "QueueUpdated refresh failed after confirmed enqueue",
                    exc_info=True,
                )

            logger.info(
                "Write request enqueued and confirmed for %s (pos=%s)",
                self._session.username,
                position,
            )
            return WriteRequestInfo(
                WriteRequestResult.WAITING,
                request_id,
                position,
                f"Waiting (position {position})",
            )
        except Exception as exc:
            logger.warning(
                "Unable to enqueue/confirm shared WRITE request for %s: %s",
                self._session.username,
                exc,
            )
            return WriteRequestInfo(
                WriteRequestResult.ERROR,
                request_id,
                0,
                "Unable to read or update the shared editing queue. Please check connectivity and try again.",
            )

    def _publish_write_granted(self, request_id: str, queue_position: int) -> None:
        self._event_bus.publish(WriteGranted(
            session_id=self._session.session_id,
            user_id=self._session.user_id,
            username=self._session.username,
            request_id=request_id,
            queue_position=queue_position,
        ))
        self._event_bus.publish(ModeChanged(mode="WRITE"))

    def initialize(self, user_id: str, username: str, role: str, runtime_version: int = 0) -> RuntimeSession:
        if self._initialized:
            logger.warning("Collaboration already initialized")
            return self._session
        self._session = RuntimeSession(user_id=user_id, username=username, role=role, runtime_version=runtime_version)
        self._heartbeat_manager = HeartbeatManager(repo=self._heartbeat_repo, session=self._session, interval_seconds=10, callback=self._on_heartbeat)
        self._heartbeat_manager.start()
        self._initialized = True
        self._event_bus.publish(SessionStarted(session_id=self._session.session_id, user_id=user_id, username=username, machine_fingerprint=self._session.machine_fingerprint, runtime_version=runtime_version))
        logger.info(f"Collaboration initialized for user {username} (session {self._session.session_id})")
        return self._session

    def shutdown(self) -> None:
        if not self._initialized:
            return
        if self._is_writing:
            self._release_write_internal()
        elif self._session is not None:
            request = self._queue_get_by_session(self._session.session_id)
            if request is not None:
                self._queue_cancel(request)
        if self._heartbeat_manager:
            self._heartbeat_manager.stop()
        if self._session:
            self._event_bus.publish(SessionEnded(session_id=self._session.session_id, reason="shutdown"))
        self._initialized = False
        self._session = None
        logger.info("Collaboration shutdown complete")

    def request_write(self, reason: str = "") -> WriteRequestInfo:
        self._ensure_initialized()
        if self._is_writing:
            return WriteRequestInfo(WriteRequestResult.GRANTED, message="Already in WRITE mode")
        request_id = str(uuid.uuid4())
        try:
            existing = self._queue_get_by_session(self._session.session_id)
        except Exception as exc:
            logger.warning(
                "Unable to read authoritative WRITE queue before request: %s",
                exc,
            )
            return WriteRequestInfo(
                WriteRequestResult.ERROR,
                request_id,
                0,
                "Unable to read the shared editing queue. Please check connectivity and try again.",
            )
        if existing:
            if self._sync_provider is not None:
                remote_lock = self._get_remote_lock_status()
                locked = remote_lock.get("locked", False)
            else:
                locked = self._lock.is_locked()
            if not locked:
                self._queue_cancel(existing)
            else:
                position = self._queue_position(self._session.session_id)
                return WriteRequestInfo(WriteRequestResult.WAITING, existing.request_id, position, f"Waiting (position {position})")

        if self._sync_provider is not None:
            remote_lock = self._get_remote_lock_status()
            locked = remote_lock.get("locked", False)
            if locked:
                remote_session_id = remote_lock.get("session_id")
                lease_expires_at = remote_lock.get("lease_expires_at")
                lease_valid = self._is_lease_valid(lease_expires_at)
                if lease_valid:
                    if remote_session_id == self._session.session_id:
                        self._is_writing = True
                        self._lock_acquired = True
                        self._sync_local_lock()
                        return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock already held by this session")
                    return self._enqueue_or_return_waiting(reason, request_id)
                lock_data = self._build_lock_data()
                acquired = self._sync_provider.acquire_lock(lock_data)
                if acquired:
                    self._is_writing = True
                    self._lock_acquired = True
                    self._lease_renewal_suspended = False
                    self._sync_local_lock()
                    self._publish_write_granted(request_id, 0)
                    logger.info(f"Write granted to {self._session.username} (expired lease replaced)")
                    return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock acquired (expired lease replaced)")
                return self._enqueue_or_return_waiting(reason, request_id)
            lock_data = self._build_lock_data()
            acquired = self._sync_provider.acquire_lock(lock_data)
            if acquired:
                self._is_writing = True
                self._lock_acquired = True
                self._lease_renewal_suspended = False
                self._sync_local_lock()
                self._publish_write_granted(request_id, 0)
                logger.info(f"Write granted to {self._session.username}")
                return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock acquired")
            return self._enqueue_or_return_waiting(reason, request_id)

        lock_data = self._lock.get_lock_info()
        if lock_data.get("locked", False):
            lock_session_id = lock_data.get("session_id")
            if self._is_lock_stale(lock_data):
                logger.warning("Stale local lock detected, cleaning up")
                self._lock._force_release()
                return self.request_write(reason)
            if lock_session_id == self._session.session_id:
                self._is_writing = True
                self._lock_acquired = True
                return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock already held by this session")
            return self._enqueue_or_return_waiting(reason, request_id)

        try:
            acquired = self._lock.acquire(self._session)
            if acquired:
                self._is_writing = True
                self._lock_acquired = True
                self._publish_write_granted(request_id, 0)
                logger.info(f"Write granted to {self._session.username} via file lock")
                return WriteRequestInfo(WriteRequestResult.GRANTED, request_id, message="Lock acquired")
            return self._enqueue_or_return_waiting(reason, request_id)
        except LockTimeoutError:
            return self._enqueue_or_return_waiting(reason, request_id)

    def release_write(self) -> bool:
        self._ensure_initialized()
        if not self._is_writing:
            logger.warning("Not in write mode")
            return False
        with self._state_mutex:
            if self._sync_provider is not None:
                result = self._sync_provider.release_lock(self._session.username)
                if not result:
                    # Keep the local WRITE projection and lease renewal alive.
                    # The transaction has not completed until the authoritative
                    # remote lock release is confirmed.
                    logger.error(
                        "Failed to release Git lock; retaining local WRITE authority for retry"
                    )
                    return False

                self._is_writing = False
                self._lock_acquired = False
                self._lease_renewal_suspended = False
                self._lock._force_release()
                self._event_bus.publish(WriteReleased(
                    session_id=self._session.session_id,
                    user_id=self._session.user_id,
                    username=self._session.username,
                ))
                self._event_bus.publish(ModeChanged(mode="READ"))
                logger.info(f"Write released by {self._session.username}")
                return True
            self._lock.release(self._session)
            self._is_writing = False
            self._lock_acquired = False
            self._lease_renewal_suspended = False
            self._event_bus.publish(WriteReleased(session_id=self._session.session_id, user_id=self._session.user_id, username=self._session.username))
            self._event_bus.publish(ModeChanged(mode="READ"))
            logger.info(f"Write released by {self._session.username}")
            return True

    def refresh_waiting_request(self, request_id: Optional[str] = None) -> bool:
        self._ensure_initialized()
        if self._session is None:
            return False
        request = self._queue_get_by_session(self._session.session_id)
        if request is None:
            return False
        if request_id and request.request_id != request_id:
            return False
        return self._queue_refresh(request)

    def has_pending_waiting_request(self, request_id: Optional[str] = None) -> bool:
        self._ensure_initialized()
        if self._session is None:
            return False
        request = self._queue_get_by_session(self._session.session_id)
        if request is None:
            return False
        return not request_id or request.request_id == request_id

    def grant_existing_waiting_request(self, request_id: Optional[str] = None) -> bool:
        self._ensure_initialized()
        if self._is_writing or self._session is None:
            return False
        request = self._queue_get_by_session(self._session.session_id)
        if request is None or (request_id and request.request_id != request_id):
            return False
        request_id = request.request_id
        queue_head = self._queue_peek()
        if queue_head is None or queue_head.request_id != request_id:
            return False

        if self._sync_provider is not None:
            remote_lock = self._get_remote_lock_status()
            if remote_lock.get("locked", False) and self._is_lease_valid(remote_lock.get("lease_expires_at")):
                return False
            lock_data = self._build_lock_data()
            if not self._sync_provider.acquire_lock(lock_data):
                return False
            self._is_writing = True
            self._lock_acquired = True
            self._sync_local_lock()
            if self._write_handoff_guard is not None:
                try:
                    if not self._write_handoff_guard():
                        self._sync_provider.release_lock(self._session.username)
                        self._lock._force_release(); self._lock_acquired = False; self._is_writing = False
                        return False
                except Exception:
                    logger.exception("Write handoff sync raised for %s", request_id)
                    try: self._sync_provider.release_lock(self._session.username)
                    finally:
                        self._lock._force_release(); self._lock_acquired = False; self._is_writing = False
                    return False
            try:
                consumed = self._queue_cancel(request)
                if not consumed:
                    # Absence is semantically consumed (for example an expired
                    # request); only fail if the request is still authoritative.
                    remaining = self._queue_get_by_session(self._session.session_id)
                    consumed = remaining is None
            except Exception:
                consumed = False

            if not consumed:
                logger.error(
                    "WRITE grant rollback: shared queue request %s could not be consumed",
                    request_id,
                )
                try:
                    self._sync_provider.release_lock(self._session.username)
                finally:
                    self._lock._force_release()
                    self._lock_acquired = False
                    self._is_writing = False
                return False

            self._event_bus.publish(WriteGranted(
                session_id=self._session.session_id,
                user_id=self._session.user_id,
                username=self._session.username,
                request_id=request_id,
                queue_position=0,
            ))
            self._event_bus.publish(ModeChanged(mode="WRITE"))
            try:
                queue_snapshot = self._queue_snapshot()
                next_request = queue_snapshot.get("next") or {}
                self._event_bus.publish(QueueUpdated(
                    queue_length=int(queue_snapshot.get("length", 0) or 0),
                    next_writer=next_request.get("username"),
                ))
            except Exception:
                # Lock ownership and queue consumption are already confirmed;
                # this event is observational only.
                logger.debug(
                    "QueueUpdated refresh failed after confirmed grant",
                    exc_info=True,
                )
            return True

        if self._lock.is_locked():
            if self._is_lock_stale(self._lock.get_lock_info()):
                self._lock._force_release()
            else:
                return False
        try:
            if not self._lock.acquire(self._session):
                return False
            self._is_writing = True; self._lock_acquired = True
            self._event_bus.publish(WriteGranted(session_id=self._session.session_id, user_id=self._session.user_id, username=self._session.username, request_id=request_id, queue_position=0))
            self._event_bus.publish(ModeChanged(mode="WRITE"))
            self._queue_cancel(request)
            self._event_bus.publish(QueueUpdated(queue_length=self._queue_count(), next_writer=self._queue_peek().username if self._queue_peek() else None))
            return True
        except LockTimeoutError:
            return False

    def _release_write_internal(self) -> bool:
        if self._sync_provider:
            result = self._sync_provider.release_lock(self._session.username)
            self._lock._force_release(); self._lock_acquired = False
            self._is_writing = False
            return result
        self._lock.release(self._session); self._lock_acquired = False; self._is_writing = False; return True

    def suspend_write_lease_renewal(self) -> None:
        """Stop automatic remote lease renewal without discarding local work.

        Used when an editing session becomes idle or its authority can no longer
        be trusted.  The transaction layer simultaneously disables write UI.
        Existing remote ownership is left untouched so the user has one lease
        window to recover; after expiry another writer may acquire normally.
        """
        with self._state_mutex:
            self._lease_renewal_suspended = True
            logger.warning("Automatic WRITE lease renewal suspended")

    def resume_write_lease_renewal(self) -> None:
        with self._state_mutex:
            self._lease_renewal_suspended = False
            logger.info("Automatic WRITE lease renewal resumed")

    def clear_local_write_projection_for_recovery(self) -> None:
        """Clear stale process-local WRITE state without releasing remote state.

        Recovery calls this only after proving the current session no longer
        owns a valid remote lease.  It prevents request_write() from returning
        the misleading 'Already in WRITE mode' result that caused the
        Renew Editing <-> Start Editing loop.
        """
        with self._state_mutex:
            if self._sync_provider is not None and self._session is not None:
                remote = self._get_remote_lock_status()
                if (
                    remote.get("locked", False)
                    and remote.get("session_id") == self._session.session_id
                    and self._is_lease_valid(remote.get("lease_expires_at"))
                ):
                    raise RuntimeError(
                        "Cannot clear local WRITE projection while this session still owns a valid remote lease."
                    )
            self._lock._force_release()
            self._lock_acquired = False
            self._is_writing = False
            self._lease_renewal_suspended = False
            logger.info("Cleared stale local WRITE projection for recovery")

    def renew_remote_lease(self, force: bool = False) -> bool:
        self._ensure_initialized()
        with self._state_mutex:
            if self._sync_provider is None or not self._is_writing or self._session is None:
                return True
            if self._lease_renewal_suspended and not force:
                logger.debug("Skipping automatic WRITE lease renewal while suspended")
                return True
            try:
                remote = self._sync_provider.remote_lock_status()
                if not remote.get("locked", False) or remote.get("session_id") != self._session.session_id:
                    return False
                lease_expires_at = remote.get("lease_expires_at")
                if not force and lease_expires_at:
                    try:
                        remaining = (datetime.fromisoformat(lease_expires_at) - datetime.now()).total_seconds()
                        if remaining > max(1.0, self._lock_timeout / 2.0): return True
                    except Exception:
                        pass
                renewed = self._sync_provider.renew_lock(self._session.username, self._session.session_id)
                if renewed:
                    self._lease_renewal_suspended = False
                    self._sync_local_lock()
                    return True
                return False
            except Exception as e:
                logger.warning(f"Remote collaboration lease renewal failed: {e}")
                return False

    def heartbeat(self) -> bool:
        self._ensure_initialized()
        if self._heartbeat_manager:
            self._heartbeat_manager.update()
            self._event_bus.publish(HeartbeatUpdated(session_id=self._session.session_id, user_id=self._session.user_id, username=self._session.username))
            if self._is_writing and self._lock_acquired:
                try:
                    current = self._lock._read_lock()
                    if current.get("locked", False):
                        current["last_heartbeat"] = datetime.now().isoformat()
                        self._lock._write_lock(current)
                except Exception as e:
                    logger.warning(f"Failed to update local lock heartbeat: {e}")
            return True
        return False

    def get_presence(self) -> Dict[str, Any]:
        self._ensure_initialized(); return self._presence.get_summary()

    def get_queue(self) -> Dict[str, Any]:
        self._ensure_initialized()
        return self._queue_snapshot()

    def get_session(self) -> Optional[RuntimeSession]: return self._session
    def is_initialized(self) -> bool: return self._initialized
    def is_writing(self) -> bool: return self._is_writing
    def _on_heartbeat(self, session: RuntimeSession) -> None: self._heartbeat_repo.update(session)
    def _ensure_initialized(self) -> None:
        if not self._initialized: raise CollaborationNotInitializedError("Collaboration not initialized. Call initialize() first.")
    def get_queue_length(self) -> int: return self._queue_count()
    def has_writer(self) -> bool: return self._is_writing or self._lock.is_locked()
    def ensure_write(self) -> bool:
        self._ensure_initialized()
        return self._is_writing and not self._lease_renewal_suspended

    def get_lock_status(self) -> Dict[str, Any]:
        if self._sync_provider is not None:
            try: return self._sync_provider.remote_lock_status()
            except Exception as e:
                logger.warning(f"Failed to get remote lock status: {e}")
                return self._get_local_lock_status()
        return self._get_local_lock_status()

    def _get_local_lock_status(self) -> Dict[str, Any]:
        lock_path = self._collab_dir / "lock.json"
        if not lock_path.exists(): return {"locked": False, "owner": None, "session_id": None}
        try:
            with open(lock_path, 'r', encoding='utf-8') as f: data = json.load(f)
            return {"locked": data.get("locked", False), "owner": data.get("username") or data.get("owner"), "session_id": data.get("session_id"), "user_id": data.get("user_id"), "acquired_at": data.get("acquired_at"), "last_heartbeat": data.get("last_heartbeat"), "lease_expires_at": data.get("lease_expires_at"), "machine": data.get("machine")}
        except Exception as e:
            logger.warning(f"Failed to read local lock status: {e}")
            return {"locked": False, "owner": None, "session_id": None}

    def get_waiting_requests(self) -> List[Dict[str, Any]]:
        return [request.to_dict() for request in self._queue_requests()]

    def cancel_waiting_request(self) -> bool:
        if not self._initialized or not self._session:
            return False
        request = self._queue_get_by_session(self._session.session_id)
        if request is None:
            # Idempotent cancel: an expired/removed request already means the
            # caller is no longer in the queue, so UI can safely leave WAITING.
            return True
        return self._queue_cancel(request)

    def get_diagnostics(self) -> Dict[str, Any]:
        self._ensure_initialized()
        lock_info = self._lock.get_lock_info() if hasattr(self._lock, 'get_lock_info') else {}
        waiting = self.get_waiting_requests()
        lock_owner = lock_info.get("username") or lock_info.get("owner")
        lock_session = lock_info.get("session_id")
        lock_lease = lock_info.get("lease_expires_at")
        is_stale = self._is_lock_stale(lock_info)
        return {"mode": "WRITE" if self._is_writing else "READ", "user": self._session.username if self._session else None, "session_id": self._session.session_id if self._session else None, "lock": {"locked": self._lock.is_locked() if hasattr(self._lock, 'is_locked') else False, "owner": lock_owner, "session_id": lock_session, "started_at": lock_info.get("acquired_at"), "last_heartbeat": lock_info.get("last_heartbeat"), "lease_expires_at": lock_lease, "is_stale": is_stale, "stale_reason": "lease expired" if is_stale else "valid"}, "session": {"active": self._is_writing, "owner": self._session.username if self._session else None, "session_id": self._session.session_id if self._session else None}, "git": {"state": "disabled" if self._sync_provider is None else "enabled"}, "heartbeat": {"is_running": self._heartbeat_manager is not None, "heartbeat_count": 0, "last_heartbeat": None, "owner": self._session.username if self._session else None}, "platform_version": 0, "deployment_profile": "standalone", "waiting_users": waiting}

    def get_health(self) -> Dict[str, Any]:
        self._ensure_initialized()
        lock_info=self._lock.get_lock_info() if hasattr(self._lock,'get_lock_info') else {}
        return {"status":"HEALTHY","details":{"mode":"WRITE" if self._is_writing else "READ","session":self._session.session_id if self._session else None,"lock":self._lock.is_locked() if hasattr(self._lock,'is_locked') else False,"lock_stale":self._is_lock_stale(lock_info),"has_lease":lock_info.get("lease_expires_at") is not None}}

    def get_lock_owner(self) -> Optional[str]: return self._lock.get_owner() if hasattr(self._lock,'get_owner') else None
    def get_session_id(self) -> Optional[str]: return self._session.session_id if self._session else None
    def has_changes(self) -> bool: return self._is_writing
    def is_lock_held_by_current_session(self) -> bool:
        if not self._lock.is_locked(): return False
        owner=self._lock.get_owner(); return owner == self._session.session_id if self._session else False
    def current_mode(self) -> str:
        self._ensure_initialized()
        return "WRITE" if self._is_writing and not self._lease_renewal_suspended else "READ"
    def get_version(self) -> int: self._ensure_initialized(); return self._lock_timeout
    def get_deployment_profile(self) -> str: self._ensure_initialized(); return "Standalone"

    def get_waiting_users(self) -> list:
        self._ensure_initialized()
        return [{"username":r.username,"priority":r.priority,"request_id":r.request_id,"session_id":r.session_id,"timestamp":r.timestamp} for r in self._queue_requests()]

    def is_next_eligible(self) -> bool:
        if not self._initialized or not self._session: return False
        next_req=self._queue_peek(); return bool(next_req and next_req.session_id == self._session.session_id)

    def is_collaboration_available(self) -> bool:
        if self._sync_provider is not None:
            try: return self._sync_provider.health()
            except Exception as e:
                logger.warning(f"Collaboration health check failed: {e}"); return False
        return True

    def get_lock_generation(self) -> int:
        if self._sync_provider is not None:
            try:
                remote=self._get_remote_lock_status()
                if remote.get("locked",False): return int(remote.get("lock_generation",0) or 0)
                return 0
            except Exception as exc:
                logger.warning("Failed to read authoritative remote lock generation: %s", exc)
        getter=getattr(self._lock,"get_lock_generation",None)
        return int(getter()) if callable(getter) else 0

    def validate_write_authority(self, session) -> Dict[str, Any]:
        result={"valid":False,"reason":"","generation":self._lock.get_lock_generation() if hasattr(self._lock,'get_lock_generation') else 0,"generation_authoritative":False,"owner":self._lock.get_owner() if hasattr(self._lock,'get_owner') else None,"lease_valid":False,"finishing_deadline":None}
        if not self._initialized or not self._session:
            result["reason"]="Not initialized or no session"; return result
        if self._sync_provider is not None:
            if not self.is_collaboration_available(): result["reason"]="Collaboration unavailable"; return result
            try:
                remote_status=self._sync_provider.remote_lock_status()
                if not remote_status.get("locked",False):
                    result["reason"]="Remote lock not held"; self._lock._force_release(); self._lock_acquired=False; self._is_writing=False; return result
                remote_session=remote_status.get("session_id")
                if remote_session != session.session_id:
                    result["reason"]=f"Remote owner mismatch: {remote_session} vs {session.session_id}"; return result
                self._sync_local_lock()
                lease_expires_at=remote_status.get("lease_expires_at")
                if self._is_lease_valid(lease_expires_at): result["lease_valid"]=True
                else: result["reason"]="Remote lock lease expired or missing"; return result
                # Reuse this authoritative observation for fencing instead of
                # issuing another remote lock read via get_lock_generation().
                result["generation"]=int(remote_status.get("lock_generation",0) or 0)
                result["generation_authoritative"]=True
                result["owner"]=remote_status.get("owner")
            except Exception as e:
                logger.warning(f"Remote lock validation failed: {e}"); result["reason"]=f"Remote validation error: {e}"; return result
        else:
            if not self._lock.is_locked(): result["reason"]="Lock not held"; return result
            current_owner=self._lock.get_owner()
            if current_owner != session.session_id:
                result["reason"]=f"Owner mismatch: lock owner={current_owner}, session={session.session_id}"; return result
        if self._is_lock_stale(self._lock.get_lock_info()):
            result["reason"]="Local lock stale"; return result
        result["valid"]=True
        if self._sync_provider is None:
            result["generation"]=self.get_lock_generation()
            result["owner"]=self._lock.get_owner() if hasattr(self._lock,'get_owner') else None
        return result
