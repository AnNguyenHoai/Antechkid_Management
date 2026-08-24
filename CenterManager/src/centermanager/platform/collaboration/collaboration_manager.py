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

        self._session: Optional[RuntimeSession] = None
        self._heartbeat_manager: Optional[HeartbeatManager] = None

        self._presence = PresenceManager(
            heartbeat_repo=self._heartbeat_repo,
            runtime_lock=self._lock,
            write_queue=self._queue,
            timeout_seconds=30,
        )

        self._initialized = False
        self._is_writing = False
        self._lock_acquired = False
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

        # REMOTE MODE: use lease_expires_at exclusively
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

        # LOCAL MODE: check finishing deadline first
        finishing_deadline = lock_data.get("finishing_deadline")
        if finishing_deadline:
            try:
                deadline = datetime.fromisoformat(finishing_deadline)
                if datetime.now() < deadline:
                    # In finishing mode and deadline not expired → valid
                    return False
            except Exception:
                pass

        # Otherwise use last_heartbeat
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
        existing = self._queue.get_by_session(self._session.session_id)
        if existing:
            position = self._queue.get_position(self._session.session_id)
            logger.info(f"Session {self._session.username} already waiting (pos={position})")
            return WriteRequestInfo(
                WriteRequestResult.WAITING,
                existing.request_id,
                position,
                f"Already waiting (position {position})"
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

        logger.info(f"Write request enqueued for {self._session.username} (pos={position})")
        return WriteRequestInfo(WriteRequestResult.WAITING, request_id, position, f"Waiting (position {position})")

    def _publish_write_granted(self, request_id: str, queue_position: int) -> None:
        self._event_bus.publish(WriteGranted(
            session_id=self._session.session_id,
            user_id=self._session.user_id,
            username=self._session.username,
            request_id=request_id,
            queue_position=queue_position,
        ))
        self._event_bus.publish(ModeChanged(mode="WRITE"))

    # ===================== Main public methods =====================

    def initialize(self, user_id: str, username: str, role: str, runtime_version: int = 0) -> RuntimeSession:
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

    def request_write(self, reason: str = "") -> WriteRequestInfo:
        """
        Request write access.

        REMOTE MODE: uses authoritative remote lock state.
        LOCAL MODE: uses local file lock.
        """
        self._ensure_initialized()

        if self._is_writing:
            return WriteRequestInfo(WriteRequestResult.GRANTED, message="Already in WRITE mode")

        request_id = str(uuid.uuid4())

        # ---- Check existing waiting request ----
        existing = self._queue.get_by_session(self._session.session_id)
        if existing:
            # Check if lock is still held (remote or local)
            if self._sync_provider is not None:
                remote_lock = self._get_remote_lock_status()
                locked = remote_lock.get("locked", False)
            else:
                locked = self._lock.is_locked()

            if not locked:
                # Lock is free, cancel stale waiting request
                self._queue.cancel(existing.request_id)
            else:
                position = self._queue.get_position(self._session.session_id)
                return WriteRequestInfo(
                    WriteRequestResult.WAITING,
                    existing.request_id,
                    position,
                    f"Waiting (position {position})"
                )

        # ---- REMOTE MODE ----
        if self._sync_provider is not None:
            remote_lock = self._get_remote_lock_status()
            locked = remote_lock.get("locked", False)

            if locked:
                remote_session_id = remote_lock.get("session_id")
                lease_expires_at = remote_lock.get("lease_expires_at")
                lease_valid = self._is_lease_valid(lease_expires_at)

                if lease_valid:
                    # Valid remote lock
                    if remote_session_id == self._session.session_id:
                        # Already owned by this session
                        self._is_writing = True
                        self._lock_acquired = True
                        self._sync_local_lock()
                        return WriteRequestInfo(
                            WriteRequestResult.GRANTED,
                            request_id,
                            message="Lock already held by this session"
                        )
                    else:
                        # Owned by another user → wait/queue
                        return self._enqueue_or_return_waiting(reason, request_id)
                else:
                    # Lease expired → attempt CAS-safe acquire (replace)
                    lock_data = self._build_lock_data()
                    acquired = self._sync_provider.acquire_lock(lock_data)
                    if acquired:
                        self._is_writing = True
                        self._lock_acquired = True
                        self._sync_local_lock()
                        self._publish_write_granted(request_id, 0)
                        logger.info(f"Write granted to {self._session.username} (expired lease replaced)")
                        return WriteRequestInfo(
                            WriteRequestResult.GRANTED,
                            request_id,
                            message="Lock acquired (expired lease replaced)"
                        )
                    else:
                        # Acquire failed (race) → enqueue
                        return self._enqueue_or_return_waiting(reason, request_id)
            else:
                # No remote lock → attempt acquire
                lock_data = self._build_lock_data()
                acquired = self._sync_provider.acquire_lock(lock_data)
                if acquired:
                    self._is_writing = True
                    self._lock_acquired = True
                    self._sync_local_lock()
                    self._publish_write_granted(request_id, 0)
                    logger.info(f"Write granted to {self._session.username}")
                    return WriteRequestInfo(
                        WriteRequestResult.GRANTED,
                        request_id,
                        message="Lock acquired"
                    )
                else:
                    return self._enqueue_or_return_waiting(reason, request_id)

        # ---- LOCAL MODE ----
        lock_data = self._lock.get_lock_info()
        if lock_data.get("locked", False):
            lock_session_id = lock_data.get("session_id")
            if self._is_lock_stale(lock_data):
                # Stale local lock → clean up locally
                logger.warning("Stale local lock detected, cleaning up")
                self._lock._force_release()
                # Retry
                return self.request_write(reason)
            if lock_session_id == self._session.session_id:
                self._is_writing = True
                self._lock_acquired = True
                return WriteRequestInfo(
                    WriteRequestResult.GRANTED,
                    request_id,
                    message="Lock already held by this session"
                )
            else:
                return self._enqueue_or_return_waiting(reason, request_id)
        else:
            # Lock free
            try:
                acquired = self._lock.acquire(self._session)
                if acquired:
                    self._is_writing = True
                    self._lock_acquired = True
                    self._publish_write_granted(request_id, 0)
                    logger.info(f"Write granted to {self._session.username} via file lock")
                    return WriteRequestInfo(
                        WriteRequestResult.GRANTED,
                        request_id,
                        message="Lock acquired"
                    )
                else:
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
                if result:
                    self._is_writing = False
                    self._lock_acquired = False
                    self._lock._force_release()
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
                    self._lock._force_release()
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
                logger.info(f"Write released by {self._session.username}")
                return True

    def refresh_waiting_request(self, request_id: Optional[str] = None) -> bool:
        """Renew this session's waiting-request lease while the client is alive."""
        self._ensure_initialized()
        if self._session is None:
            return False
        request = self._queue.get_by_session(self._session.session_id)
        if request is None:
            return False
        if request_id and request.request_id != request_id:
            return False
        return self._queue.refresh(request.request_id)

    def has_pending_waiting_request(self, request_id: Optional[str] = None) -> bool:
        """Return whether this session still owns its waiting request."""
        self._ensure_initialized()
        if self._session is None:
            return False
        request = self._queue.get_by_session(self._session.session_id)
        if request is None:
            return False
        return not request_id or request.request_id == request_id

    def grant_existing_waiting_request(self, request_id: Optional[str] = None) -> bool:
        """Grant WRITE lock to the existing waiting request."""
        self._ensure_initialized()
        if self._is_writing:
            logger.info("Already writing, cannot grant waiting request")
            return False
        if self._session is None:
            logger.warning("No session, cannot grant waiting request")
            return False

        # Always resolve the request from the current session.  The caller's
        # request_id is only an identity guard; the local queue can be refreshed
        # asynchronously after a remote handoff and must not be treated as an
        # authority that the request has permanently disappeared.
        request = self._queue.get_by_session(self._session.session_id)
        if request is None:
            logger.info("No pending request for session %s", self._session.session_id)
            return False
        if request_id and request.request_id != request_id:
            logger.info(
                "Waiting request identity changed from %s to %s; retaining WAITING",
                request_id,
                request.request_id,
            )
            return False
        request_id = request.request_id

        # A waiting writer may only be granted when it is the current queue
        # head.  This check is intentionally performed before lock acquisition
        # so a later waiter cannot bypass an earlier waiter during handoff.
        queue_head = self._queue.peek()
        if queue_head is None:
            logger.info("No queue head, cannot grant waiting request")
            return False
        if queue_head.request_id != request_id:
            logger.info(
                "Waiting request %s is not queue head (%s), cannot grant",
                request_id,
                queue_head.request_id,
            )
            return False

        # ---- Remote mode: check remote state ----
        if self._sync_provider is not None:
            remote_lock = self._get_remote_lock_status()
            locked = remote_lock.get("locked", False)
            if locked:
                lease_expires_at = remote_lock.get("lease_expires_at")
                lease_valid = self._is_lease_valid(lease_expires_at)
                if lease_valid:
                    # Valid remote lock held by someone else
                    logger.info("Remote lock is still valid, cannot grant")
                    return False
                else:
                    # Lease expired, we can try to acquire
                    pass
            # Lock is free or expired → try to acquire
            lock_data = self._build_lock_data()
            acquired = self._sync_provider.acquire_lock(lock_data)
            if acquired:
                self._is_writing = True
                self._lock_acquired = True
                self._sync_local_lock()

                # Handoff invariant: a queued writer must synchronize its local
                # runtime snapshot before it becomes EDITING. Keep the queue entry
                # intact if synchronization fails so the request can be retried.
                if self._write_handoff_guard is not None:
                    try:
                        logger.info(
                            "Write handoff: syncing runtime before granting request %s",
                            request_id,
                        )
                        if not self._write_handoff_guard():
                            logger.warning(
                                "Write handoff sync failed for %s; releasing lock and retaining queue entry",
                                request_id,
                            )
                            try:
                                self._sync_provider.release_lock(self._session.username)
                            finally:
                                self._lock._force_release()
                                self._lock_acquired = False
                                self._is_writing = False
                            return False
                    except Exception as exc:
                        logger.exception("Write handoff sync raised for %s: %s", request_id, exc)
                        try:
                            self._sync_provider.release_lock(self._session.username)
                        finally:
                            self._lock._force_release()
                            self._lock_acquired = False
                            self._is_writing = False
                        return False

                # Notify the waiting transaction before consuming its queue entry.
                # This prevents a concurrent UI poll from seeing the removed request
                # and transitioning WAITING -> IDLE before the grant is applied.
                self._event_bus.publish(WriteGranted(
                    session_id=self._session.session_id,
                    user_id=self._session.user_id,
                    username=self._session.username,
                    request_id=request_id,
                    queue_position=0,
                ))
                self._event_bus.publish(ModeChanged(mode="WRITE"))
                self._queue.cancel(request_id)
                self._event_bus.publish(QueueUpdated(
                    queue_length=self._queue.count(),
                    next_writer=self._queue.peek().username if self._queue.peek() else None,
                ))
                logger.info(f"Granted write to waiting request {request_id}")
                return True
            else:
                logger.warning("Failed to acquire lock for waiting request")
                return False

        # ---- Local mode ----
        if self._lock.is_locked():
            if self._is_lock_stale(self._lock.get_lock_info()):
                self._lock._force_release()
            else:
                logger.info("Lock is still held by someone else, cannot grant")
                return False

        # Lock is free → acquire
        try:
            acquired = self._lock.acquire(self._session)
            if acquired:
                self._is_writing = True
                self._lock_acquired = True
                # Same ordering guarantee as remote mode.
                self._event_bus.publish(WriteGranted(
                    session_id=self._session.session_id,
                    user_id=self._session.user_id,
                    username=self._session.username,
                    request_id=request_id,
                    queue_position=0,
                ))
                self._event_bus.publish(ModeChanged(mode="WRITE"))
                self._queue.cancel(request_id)
                self._event_bus.publish(QueueUpdated(
                    queue_length=self._queue.count(),
                    next_writer=self._queue.peek().username if self._queue.peek() else None,
                ))
                logger.info(f"Granted write to waiting request {request_id}")
                return True
            else:
                logger.warning("Failed to acquire local lock for waiting request")
                return False
        except LockTimeoutError:
            logger.warning("Lock acquisition timed out for waiting request")
            return False

    def _release_write_internal(self) -> bool:
        if self._sync_provider:
            result = self._sync_provider.release_lock(self._session.username)
            self._lock._force_release()
            self._lock_acquired = False
            return result
        else:
            self._lock.release(self._session)
            self._lock_acquired = False
            return True

    def renew_remote_lease(self, force: bool = False) -> bool:
        """Renew this session's authoritative remote collaboration lease.

        Renewal is deliberately owned by the collaboration lifecycle, not by
        MAIN synchronization.  It is safe to call from the poller because the
        synchronization provider performs owner/session/CAS validation.

        Returns True when no renewal is required or when renewal succeeds.
        Returns False when this session is not writing, the lease is no longer
        valid, or the remote renewal fails.
        """
        self._ensure_initialized()
        if self._sync_provider is None or not self._is_writing or self._session is None:
            return True

        try:
            remote = self._sync_provider.remote_lock_status()
            if not remote.get("locked", False):
                logger.warning("Active writer has no remote lock; lease renewal skipped")
                return False

            if remote.get("session_id") != self._session.session_id:
                logger.warning(
                    "Active writer lease ownership changed: remote_session=%s local_session=%s",
                    remote.get("session_id"), self._session.session_id,
                )
                return False

            lease_expires_at = remote.get("lease_expires_at")
            if not force and lease_expires_at:
                try:
                    expires = datetime.fromisoformat(lease_expires_at)
                    remaining = (expires - datetime.now()).total_seconds()
                    # Renew at half-life. This leaves a full poll interval of
                    # tolerance while avoiding a Git commit on every poll.
                    renewal_threshold = max(1.0, self._lock_timeout / 2.0)
                    if remaining > renewal_threshold:
                        return True
                except Exception:
                    # Invalid/missing expiry must be treated conservatively:
                    # attempt renewal and let the provider validate authority.
                    pass

            renewed = self._sync_provider.renew_lock(
                self._session.username,
                self._session.session_id,
            )
            if renewed:
                # Keep the local collaboration mirror aligned with the
                # authoritative remote lock. This does not touch MAIN Git.
                self._sync_local_lock()
                logger.debug("Remote collaboration lease renewed")
                return True

            logger.warning("Remote collaboration lease renewal failed")
            return False
        except Exception as e:
            logger.warning(f"Remote collaboration lease renewal failed: {e}")
            return False

    def heartbeat(self) -> bool:
        self._ensure_initialized()
        if self._heartbeat_manager:
            self._heartbeat_manager.update()
            self._event_bus.publish(HeartbeatUpdated(
                session_id=self._session.session_id,
                user_id=self._session.user_id,
                username=self._session.username,
            ))
            if self._is_writing and self._lock_acquired:
                try:
                    current = self._lock._read_lock()
                    if current.get("locked", False):
                        current["last_heartbeat"] = datetime.now().isoformat()
                        self._lock._write_lock(current)
                        logger.debug(f"Lock heartbeat updated: {current['last_heartbeat']}")
                except Exception as e:
                    logger.warning(f"Failed to update local lock heartbeat: {e}")
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

    def get_lock_status(self) -> Dict[str, Any]:
        if self._sync_provider is not None:
            try:
                return self._sync_provider.remote_lock_status()
            except Exception as e:
                logger.warning(f"Failed to get remote lock status: {e}")
                return self._get_local_lock_status()
        else:
            return self._get_local_lock_status()

    def _get_local_lock_status(self) -> Dict[str, Any]:
        lock_path = self._collab_dir / "lock.json"
        if not lock_path.exists():
            return {"locked": False, "owner": None, "session_id": None}
        try:
            with open(lock_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {
                "locked": data.get("locked", False),
                "owner": data.get("username") or data.get("owner"),
                "session_id": data.get("session_id"),
                "user_id": data.get("user_id"),
                "acquired_at": data.get("acquired_at"),
                "last_heartbeat": data.get("last_heartbeat"),
                "lease_expires_at": data.get("lease_expires_at"),
                "machine": data.get("machine"),
            }
        except Exception as e:
            logger.warning(f"Failed to read local lock status: {e}")
            return {"locked": False, "owner": None, "session_id": None}

    def get_waiting_requests(self) -> List[Dict[str, Any]]:
        if not self._queue_dir.exists():
            return []
        requests = []
        for file in self._queue_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get("status") == "pending":
                    requests.append(data)
            except Exception:
                continue
        return requests

    def cancel_waiting_request(self) -> bool:
        if not self._initialized or not self._session:
            return False
        request = self._queue.get_by_session(self._session.session_id)
        if request:
            self._queue.cancel(request.request_id)
            return True
        return False

    def get_diagnostics(self) -> Dict[str, Any]:
        self._ensure_initialized()
        lock_info = self._lock.get_lock_info() if hasattr(self._lock, 'get_lock_info') else {}
        waiting = self.get_waiting_requests()

        lock_owner = lock_info.get("username") or lock_info.get("owner")
        lock_session = lock_info.get("session_id")
        lock_lease = lock_info.get("lease_expires_at")

        is_stale = self._is_lock_stale(lock_info)

        return {
            "mode": "WRITE" if self._is_writing else "READ",
            "user": self._session.username if self._session else None,
            "session_id": self._session.session_id if self._session else None,
            "lock": {
                "locked": self._lock.is_locked() if hasattr(self._lock, 'is_locked') else False,
                "owner": lock_owner,
                "session_id": lock_session,
                "started_at": lock_info.get("acquired_at"),
                "last_heartbeat": lock_info.get("last_heartbeat"),
                "lease_expires_at": lock_lease,
                "is_stale": is_stale,
                "stale_reason": "lease expired" if is_stale else "valid",
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
            "waiting_users": waiting,
        }

    def get_health(self) -> Dict[str, Any]:
        self._ensure_initialized()
        lock_info = self._lock.get_lock_info() if hasattr(self._lock, 'get_lock_info') else {}
        is_stale = self._is_lock_stale(lock_info)
        return {
            "status": "HEALTHY",
            "details": {
                "mode": "WRITE" if self._is_writing else "READ",
                "session": self._session.session_id if self._session else None,
                "lock": self._lock.is_locked() if hasattr(self._lock, 'is_locked') else False,
                "lock_stale": is_stale,
                "has_lease": lock_info.get("lease_expires_at") is not None,
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

    def is_collaboration_available(self) -> bool:
        if self._sync_provider is not None:
            try:
                return self._sync_provider.health()
            except Exception as e:
                logger.warning(f"Collaboration health check failed: {e}")
                return False
        return True

    def validate_write_authority(self, session) -> Dict[str, Any]:
        """
        Validate write authority for a session.

        Order of checks (MANDATORY):
        1. Collaboration availability (remote mode)
        2. Remote lock exists and owner/session match
        3. lease_expires_at valid (remote mode) OR local lock valid
        4. Finishing deadline (if applicable)
        """
        result = {
            "valid": False,
            "reason": "",
            "generation": self._lock.get_lock_generation() if hasattr(self._lock, 'get_lock_generation') else 0,
            "owner": self._lock.get_owner() if hasattr(self._lock, 'get_owner') else None,
            "lease_valid": False,
            "finishing_deadline": None,
        }

        if not self._initialized or not self._session:
            result["reason"] = "Not initialized or no session"
            return result

        # ---- REMOTE MODE ----
        if self._sync_provider is not None:
            if not self.is_collaboration_available():
                result["reason"] = "Collaboration unavailable"
                return result

            try:
                remote_status = self._sync_provider.remote_lock_status()
                if not remote_status.get("locked", False):
                    result["reason"] = "Remote lock not held"
                    self._lock._force_release()
                    self._lock_acquired = False
                    self._is_writing = False
                    return result

                remote_session = remote_status.get("session_id")
                if remote_session != session.session_id:
                    result["reason"] = f"Remote owner mismatch: {remote_session} vs {session.session_id}"
                    return result

                # Sync local lock from remote
                self._sync_local_lock()

                # Check lease validity
                lease_expires_at = remote_status.get("lease_expires_at")
                if self._is_lease_valid(lease_expires_at):
                    result["lease_valid"] = True
                else:
                    result["reason"] = "Remote lock lease expired or missing"
                    return result

            except Exception as e:
                logger.warning(f"Remote lock validation failed: {e}")
                result["reason"] = f"Remote validation error: {e}"
                return result

        # ---- LOCAL MODE ----
        else:
            if not self._lock.is_locked():
                result["reason"] = "Lock not held"
                return result

            current_owner = self._lock.get_owner()
            if current_owner != session.session_id:
                result["reason"] = f"Owner mismatch: lock owner={current_owner}, session={session.session_id}"
                return result

            lock_info = self._lock.get_lock_info()
            if self._is_lock_stale(lock_info):
                result["reason"] = "Lock is stale (heartbeat timeout or finishing expired)"
                return result

            result["lease_valid"] = True

        # ---- CHECK FINISHING DEADLINE ----
        lock_info = self._lock.get_lock_info()
        deadline = self._lock.get_finishing_deadline()
        result["finishing_deadline"] = deadline

        if deadline is not None:
            if datetime.now() >= deadline:
                result["reason"] = "Finishing deadline expired"
                return result
            result["valid"] = True
            return result

        result["valid"] = True
        return result

    def get_collaboration_state(self) -> Dict[str, Any]:
        lock_info = self._lock.get_lock_info()
        return {
            "locked": lock_info.get("locked", False),
            "owner": lock_info.get("owner"),
            "session_id": lock_info.get("session_id"),
            "lock_generation": lock_info.get("lock_generation", 0),
            "lease_revision": lock_info.get("lease_revision", 0),
            "finishing_started_at": lock_info.get("finishing_started_at"),
            "finishing_deadline": lock_info.get("finishing_deadline"),
            "publish_intent": lock_info.get("publish_intent", False),
            "last_heartbeat": lock_info.get("last_heartbeat"),
            "lease_expires_at": lock_info.get("lease_expires_at"),
        }