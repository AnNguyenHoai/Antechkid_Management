# -*- coding: utf-8 -*-
"""Exclusive recovery authority for destructive runtime recovery operations.

Recovery deliberately does not enter the normal CollaborationManager WRITE mode.
It borrows the same distributed exclusion primitive so normal editors cannot
start while a restore is in progress, while keeping recovery lifecycle separate
from Start Editing / Finish Editing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RecoveryAuthorityError(RuntimeError):
    """Recovery authority could not be acquired or was lost."""


@dataclass
class RecoveryAuthority:
    manager: Any
    _acquired: bool = False
    _session_id: Optional[str] = None
    _username: Optional[str] = None

    def acquire(self) -> bool:
        manager = self.manager
        if manager is None or not manager.is_initialized():
            raise RecoveryAuthorityError("Collaboration session is not initialized.")
        if manager.is_writing():
            raise RecoveryAuthorityError(
                "Finish or cancel the current editing session before starting recovery."
            )

        session = manager.get_session()
        if session is None:
            raise RecoveryAuthorityError("Collaboration session is unavailable.")

        with manager._state_mutex:
            if manager._sync_provider is not None:
                remote = manager._get_remote_lock_status()
                if remote.get("locked", False) and manager._is_lease_valid(
                    remote.get("lease_expires_at")
                ):
                    raise RecoveryAuthorityError(
                        "Recovery cannot start while another exclusive operation is active."
                    )
                lock_data = manager._build_lock_data()
                lock_data["authority_mode"] = "RECOVERY"
                lock_data["reason"] = "backup_restore"
                if not manager._sync_provider.acquire_lock(lock_data):
                    raise RecoveryAuthorityError(
                        "Unable to acquire exclusive recovery authority."
                    )
                manager._lock._write_lock(lock_data)
            else:
                current = manager._lock.get_lock_info()
                if current.get("locked", False):
                    if manager._is_lock_stale(current):
                        manager._lock._force_release()
                    else:
                        raise RecoveryAuthorityError(
                            "Recovery cannot start while another exclusive operation is active."
                        )
                if not manager._lock.acquire(session, timeout_seconds=0):
                    raise RecoveryAuthorityError(
                        "Unable to acquire exclusive recovery authority."
                    )
                current = manager._lock.get_lock_info()
                current["authority_mode"] = "RECOVERY"
                current["reason"] = "backup_restore"
                manager._lock._write_lock(current)

            # Intentionally do NOT set CollaborationManager._is_writing. Recovery
            # is an independent destructive-operation authority, not edit mode.
            # Capture the acquisition principal so later validation cannot silently
            # follow a replaced/reinitialized collaboration session.
            self._session_id = str(session.session_id)
            self._username = str(session.username)
            self._acquired = True
            logger.info("Exclusive recovery authority acquired by %s", session.username)
            return True

    def validate(self) -> bool:
        if not self._acquired or not self._session_id or not self._username:
            return False
        manager = self.manager
        session = manager.get_session() if manager is not None else None
        if session is None:
            return False
        if (
            str(getattr(session, "session_id", "")) != self._session_id
            or str(getattr(session, "username", "")) != self._username
        ):
            return False

        try:
            if manager._sync_provider is not None:
                status = manager._get_remote_lock_status()
                # GitSynchronizationProvider persists the complete lock payload,
                # including authority_mode=RECOVERY, on the isolated lock branch.
                # Its public remote_lock_status() projection historically omitted
                # authority_mode/reason. An absent projected mode therefore cannot
                # by itself mean that a freshly acquired recovery lease was lost.
                # If a provider does expose a mode, it must still be RECOVERY.
                projected_mode = status.get("authority_mode")
                if projected_mode not in (None, "", "RECOVERY"):
                    return False

                # In remote mode the distributed lease is authoritative. Do not
                # trust CollaborationManager._is_writing here: background local
                # projection can transiently mark this process' own recovery lease
                # as WRITE even though no WRITE lease was acquired. Session identity,
                # owner and lease validity fence the destructive operation.
                owner = status.get("owner") or status.get("username")
                return bool(
                    status.get("locked", False)
                    and str(status.get("session_id") or "") == self._session_id
                    and str(owner or "") == self._username
                    and manager._is_lease_valid(status.get("lease_expires_at"))
                )

            # Local-only mode has the complete lock file, so retain the strict
            # RECOVERY mode check and reject any concurrent WRITE state.
            if manager.is_writing():
                return False
            status = manager._lock.get_lock_info()
            owner = status.get("owner") or status.get("username")
            return bool(
                status.get("locked", False)
                and str(status.get("session_id") or "") == self._session_id
                and str(owner or "") == self._username
                and status.get("authority_mode") == "RECOVERY"
            )
        except Exception:
            logger.exception("Failed to validate recovery authority")
            return False

    def renew(self) -> bool:
        """Renew remote recovery lease before entering the destructive boundary."""
        if not self.validate():
            return False
        manager = self.manager
        if manager._sync_provider is None:
            return True
        session = manager.get_session()
        if session is None:
            return False
        try:
            renewed = manager._sync_provider.renew_lock(session.username, session.session_id)
            return bool(renewed and self.validate())
        except Exception:
            logger.exception("Failed to renew recovery authority")
            return False

    def release(self) -> None:
        if not self._acquired:
            return
        manager = self.manager
        session = manager.get_session() if manager is not None else None
        try:
            with manager._state_mutex:
                if manager._sync_provider is not None:
                    if session is not None:
                        manager._sync_provider.release_lock(session.username)
                    manager._lock._force_release()
                elif session is not None:
                    manager._lock.release(session)
        finally:
            self._acquired = False
            self._session_id = None
            self._username = None
            logger.info("Exclusive recovery authority released")

    def __enter__(self) -> "RecoveryAuthority":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
