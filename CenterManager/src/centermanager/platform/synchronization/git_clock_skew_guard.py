"""Clock-skew policy for reclaiming distributed Git write-lock leases."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

# A remote lease owned by another runtime is intentionally protected for this
# extra interval after its wall-clock expiry. This handles the case where the
# contender's Windows clock is ahead of the lock owner's clock without changing
# the core meaning of ``_is_lock_valid``.
DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS = 10 * 60


def is_remote_write_lock_reclaimable(
    remote_lock: Dict[str, Any],
    contender_lock: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    tolerance_seconds: int = DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS,
) -> bool:
    """Return whether a contender may reclaim an observed remote WRITE lock.

    Lock validity and stale-lock reclamation are deliberately separate policies:
    ``GitSynchronizationProvider._is_lock_valid`` remains strict and reports an
    expired lease as invalid immediately. Only acquisition of an expired lock
    owned by another runtime gets a bounded clock-skew safety window.

    A matching non-empty ``session_id`` identifies the same runtime/session and
    can reclaim its own expired lease immediately. Missing/mismatched session IDs
    fail closed inside the grace window. Malformed/missing expiry keeps the
    provider's historical stale-lock behavior and is reclaimable.
    """
    if not remote_lock.get("locked", False):
        return True

    lease_expires_at = remote_lock.get("lease_expires_at")
    if not lease_expires_at:
        return True

    try:
        expires = datetime.fromisoformat(str(lease_expires_at))
    except (TypeError, ValueError, OverflowError):
        return True

    current_time = now or datetime.now()

    # A genuinely live lease is never reclaimable here, regardless of session.
    if current_time < expires:
        return False

    remote_session = remote_lock.get("session_id")
    contender_session = contender_lock.get("session_id")
    if remote_session and contender_session and remote_session == contender_session:
        return True

    tolerance_seconds = max(0, int(tolerance_seconds))
    grace_deadline = expires + timedelta(seconds=tolerance_seconds)
    return current_time >= grace_deadline


def install_lock_clock_skew_guard(
    provider_cls: Any,
    tolerance_seconds: int = DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS,
) -> None:
    """Install a reclaim policy while leaving generic lock validity untouched.

    The actual acquisition implementation (including the diagnostics layer)
    consults ``_is_remote_write_lock_reclaimable`` only after strict validity
    reports the observed lease expired. This avoids wrapper-order bugs where a
    later compatibility layer replaces ``acquire_lock`` and silently bypasses
    clock-skew protection.
    """
    if getattr(provider_cls, "_clock_skew_guard_installed", False):
        return

    tolerance_seconds = max(0, int(tolerance_seconds))

    def remote_write_lock_reclaimable(
        self,
        remote_lock: Dict[str, Any],
        contender_lock: Dict[str, Any],
    ) -> bool:
        return is_remote_write_lock_reclaimable(
            remote_lock,
            contender_lock,
            tolerance_seconds=tolerance_seconds,
        )

    provider_cls._is_remote_write_lock_reclaimable = remote_write_lock_reclaimable
    provider_cls._clock_skew_guard_installed = True
    provider_cls._clock_skew_tolerance_seconds = tolerance_seconds
