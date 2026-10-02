"""Clock-skew guard for reclaiming distributed Git write-lock leases."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

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
    expired lease as invalid immediately.  Only acquisition of an expired lock
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
    """Guard only stale remote WRITE-lock reclamation against clock skew.

    The provider's generic ``_is_lock_valid`` contract is intentionally left
    untouched: once ``lease_expires_at`` is in the past the lease is invalid.
    This installer wraps ``acquire_lock`` instead, so only the decision to take
    over an expired remote WRITE lock from another runtime receives the bounded
    grace period.

    The wrapper preserves the provider's existing atomic CAS path: it reads one
    remote OID, evaluates the lock represented by that OID, creates a child lock
    commit, and pushes with ``--force-with-lease`` against the same expected OID.
    """
    if getattr(provider_cls, "_clock_skew_guard_installed", False):
        return

    tolerance_seconds = max(0, int(tolerance_seconds))

    def acquire_lock_with_clock_skew_guard(self, lock_data: dict) -> bool:
        logger.info(
            "Atomic lock acquisition started: owner=%s",
            lock_data.get("owner"),
        )
        try:
            expected_oid = self._remote_lock_oid()
            if expected_oid is not None:
                # Fetch lock branch to ensure the observed parent OID is local.
                self._fetch_lock_branch()
                remote_lock = self._read_lock_from_oid(expected_oid)

                # Keep the provider's strict validity semantics unchanged.
                if self._is_lock_valid(remote_lock):
                    owner = remote_lock.get("owner", "unknown")
                    logger.info(
                        "Lock already held by %s, acquisition denied",
                        owner,
                    )
                    return False

                if not is_remote_write_lock_reclaimable(
                    remote_lock,
                    lock_data,
                    tolerance_seconds=tolerance_seconds,
                ):
                    owner = remote_lock.get("owner", "unknown")
                    logger.warning(
                        "Expired remote WRITE lock owned by %s is inside the "
                        "clock-skew safety window; acquisition denied",
                        owner,
                    )
                    return False

            # Preserve the provider's normal lease generation.
            lock_data["lease_expires_at"] = (
                datetime.now() + timedelta(seconds=self._lease_duration_seconds)
            ).isoformat()

            # Create a lock commit without checking out the lock branch.
            commit_sha = self._create_lock_commit_plumbing(lock_data, expected_oid)
            if not commit_sha:
                logger.error("Failed to create lock commit")
                return False

            # Atomic compare-and-swap against the exact OID evaluated above.
            if not self._push_lock_branch(commit_sha, expected_oid):
                logger.error("Failed to push lock branch")
                return False

            # Verify final ownership exactly as the provider normally does.
            new_oid = self._remote_lock_oid()
            if new_oid is not None:
                remote_verify = self._read_lock_from_oid(new_oid)
                if remote_verify.get("session_id") == lock_data.get("session_id"):
                    logger.info(
                        "Atomic lock acquired successfully: session=%s",
                        lock_data.get("session_id"),
                    )
                    return True

                logger.warning(
                    "Lock push succeeded but ownership verification failed"
                )
                return False

            logger.error("Lock push succeeded but remote OID disappeared")
            return False

        except Exception as exc:
            logger.exception("Lock acquisition failed: %s", exc)
            return False

    provider_cls.acquire_lock = acquire_lock_with_clock_skew_guard
    provider_cls._clock_skew_guard_installed = True
    provider_cls._clock_skew_tolerance_seconds = tolerance_seconds
