"""False-WAITING protection for remote collaboration.

This module deliberately wraps the existing CollaborationManager request path
instead of rewriting CollaborationManager. The restored manager remains the
source of truth for queue arbitration and lock ownership.

A WAITING result is valid only when an authoritative remote lock belongs to a
*different session* and its lease is still active. If the manager reports
WAITING while the remote lock is free or expired, retry the existing request
path once. If it still cannot acquire the lock, return ERROR rather than
creating a misleading WAITING state.
"""

from datetime import datetime
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def _lease_is_active(lock_data: dict) -> bool:
    if not lock_data.get("locked", False):
        return False
    lease = lock_data.get("lease_expires_at")
    if not lease:
        return False
    try:
        return datetime.now() < datetime.fromisoformat(lease)
    except (TypeError, ValueError):
        return False


def install_false_waiting_guard(manager_cls) -> None:
    """Install the guard once on the restored CollaborationManager class."""
    if getattr(manager_cls, "_false_waiting_guard_installed", False):
        return

    original = manager_cls.request_write

    @wraps(original)
    def guarded_request_write(self, reason: str = ""):
        result = original(self, reason)
        if getattr(result, "result", None) is None:
            return result

        # Never interfere with a genuine grant, rejection, or error.
        if result.result.value != "waiting":
            return result

        # Local-mode collaboration has no authoritative remote lease. Keep the
        # original local queue semantics untouched.
        provider = getattr(self, "_sync_provider", None)
        if provider is None:
            return result

        try:
            remote = self._get_remote_lock_status()
            session_id = getattr(getattr(self, "_session", None), "session_id", None)
            owner_session = remote.get("session_id")

            # WAITING is legitimate only for another session with an active
            # lease. A free/stale/invalid lock must not produce WAITING.
            if owner_session != session_id and _lease_is_active(remote):
                return result

            logger.warning(
                "False WAITING detected for session=%s: remote lock is not actively "
                "held by another session; retrying acquisition",
                session_id,
            )

            retry = original(self, reason)
            if retry.result.value != "waiting":
                return retry

            # If acquisition still failed while there is no active competing
            # lease, surface an explicit error instead of misleading the UI.
            remote_after = self._get_remote_lock_status()
            if not _lease_is_active(remote_after):
                from .collaboration_manager import WriteRequestInfo, WriteRequestResult
                return WriteRequestInfo(
                    WriteRequestResult.ERROR,
                    getattr(retry, "request_id", ""),
                    0,
                    "Write lock is currently unavailable; no active writer was detected. Please retry.",
                )
            return retry
        except Exception:
            # Safety first: do not manufacture a WAITING state when the
            # authoritative state cannot be inspected. Return the original
            # result so existing error handling remains intact.
            logger.exception("False-WAITING guard failed while inspecting remote lock")
            return result

    manager_cls.request_write = guarded_request_write
    manager_cls._false_waiting_guard_installed = True
