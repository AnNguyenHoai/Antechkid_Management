# -*- coding: utf-8 -*-
"""Compatibility normalization for FINISHING authority validation.

The collaboration manager owns the lock and transaction state, but legacy
callers still consume the authority dictionary.  Keep the normalization at
the collaboration package boundary so the authority contract remains stable:

* expose the persisted FINISHING deadline;
* an expired FINISHING deadline always wins over heartbeat staleness;
* in normal EDITING, a stale heartbeat is reported as a heartbeat timeout.

This deliberately does not grant or revoke any capability and does not alter
lock acquisition semantics.
"""

from datetime import datetime
from typing import Any, Dict


_INSTALL_SENTINEL = "_finishing_authority_compat_installed"


def install_finishing_authority_compat(collaboration_manager_cls: type) -> None:
    """Install the narrow FINISHING authority response normalization once."""
    if getattr(collaboration_manager_cls, _INSTALL_SENTINEL, False):
        return

    original_validate = collaboration_manager_cls.validate_write_authority

    def validate_write_authority(self, session) -> Dict[str, Any]:
        result = original_validate(self, session)

        lock = getattr(self, "_lock", None)
        if lock is None:
            return result

        # Remote mode has two independent clocks:
        #   * lease_expires_at fences ownership of the remote lock;
        #   * finishing_deadline fences the FINISHING transaction.
        # The base validator checks the lease, but its generic local-stale
        # compatibility path cannot see the remote FINISHING deadline because
        # the remote branch returns before the local lock-stale evaluation.
        # Read the remote authority directly so an expired FINISHING deadline
        # cannot be reported as a valid write authority while the lease itself
        # is still alive.
        if getattr(self, "_sync_provider", None) is not None:
            if not result.get("valid", False):
                # Preserve stronger failures from the authoritative remote
                # validator (owner mismatch, expired lease, unavailable sync).
                return result
            try:
                remote_status = self._sync_provider.remote_lock_status()
                deadline = _parse_datetime(remote_status.get("finishing_deadline"))
                if deadline is None:
                    return result

                result["finishing_deadline"] = deadline
                if datetime.now() >= deadline:
                    result["valid"] = False
                    result["reason"] = "Deadline expired"
                    return result

                # FINISHING's absolute deadline is authoritative while active;
                # a stale heartbeat must not invalidate the transaction before
                # that deadline. The remote lease was already validated by the
                # base validator above.
                result["valid"] = True
                if not result.get("reason") or result.get("reason") == "Local lock stale":
                    result["reason"] = "OK"
                return result
            except Exception:
                # Do not weaken the base validator when remote metadata cannot
                # be inspected. Its result remains authoritative.
                return result

        try:
            lock_info = lock.get_lock_info()
        except Exception:
            return result

        deadline = _parse_datetime(lock_info.get("finishing_deadline"))
        if deadline is not None:
            # Preserve the public authority contract: callers must be able to
            # observe the active absolute FINISHING deadline.
            result["finishing_deadline"] = deadline

            if datetime.now() >= deadline:
                result["valid"] = False
                result["reason"] = "Deadline expired"
                return result

            # An active FINISHING deadline fences heartbeat staleness.  This
            # mirrors the lock's finishing semantics and is intentionally
            # independent of the normal EDITING heartbeat timeout.
            result["valid"] = True
            if not result.get("reason") or result.get("reason") == "Local lock stale":
                result["reason"] = "OK"
            return result

        # No finishing deadline means the transaction is in normal EDITING
        # semantics. If the base validator reports a stale local lock, surface
        # the actual authority failure that caused it.
        if not result.get("valid") and result.get("reason") == "Local lock stale":
            last_heartbeat = _parse_datetime(lock_info.get("last_heartbeat"))
            if last_heartbeat is not None:
                age = (datetime.now() - last_heartbeat).total_seconds()
                timeout = float(getattr(self, "_lock_timeout", 60))
                if age > timeout:
                    result["reason"] = "Heartbeat timeout"

        return result

    collaboration_manager_cls.validate_write_authority = validate_write_authority
    setattr(collaboration_manager_cls, _INSTALL_SENTINEL, True)


def _parse_datetime(value: Any):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
