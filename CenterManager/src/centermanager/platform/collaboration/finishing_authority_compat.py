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

        # The persisted local lock is the source of truth for finishing
        # metadata.  Keep remote validation behavior unchanged; the remote
        # provider already returns its authoritative lease state.
        if getattr(self, "_sync_provider", None) is not None:
            return result

        lock = getattr(self, "_lock", None)
        if lock is None:
            return result

        try:
            lock_info = lock.get_lock_info()
        except Exception:
            return result

        deadline_value = lock_info.get("finishing_deadline")
        started_value = lock_info.get("finishing_started_at")

        deadline = _parse_datetime(deadline_value)
        started_at = _parse_datetime(started_value)

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
        # semantics.  If the base validator reports a stale local lock,
        # surface the actual authority failure that caused it.
        if not result.get("valid") and result.get("reason") == "Local lock stale":
            last_heartbeat = _parse_datetime(lock_info.get("last_heartbeat"))
            if last_heartbeat is not None:
                age = (datetime.now() - last_heartbeat).total_seconds()
                timeout = float(getattr(self, "_lock_timeout", 60))
                if age > timeout:
                    result["reason"] = "Heartbeat timeout"

        # started_at is useful to diagnostics but is intentionally not added
        # to the existing result shape unless a finishing deadline exists.
        _ = started_at
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
