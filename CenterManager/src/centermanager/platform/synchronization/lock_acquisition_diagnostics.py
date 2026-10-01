"""Write-lock acquisition diagnostics for GitSynchronizationProvider.

This compatibility layer keeps the existing provider implementation intact while
making lock-acquisition failures observable.  A failed acquisition is classified
as either real contention (another valid remote lease exists) or an operational
failure such as commit creation, push rejection, or ownership verification.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def install_lock_acquisition_diagnostics(provider_cls) -> None:
    """Install precise lock-acquisition failure reporting once."""
    if getattr(provider_cls, "_lock_acquisition_diagnostics_installed", False):
        return

    def get_last_lock_error(self) -> str:
        return str(getattr(self, "_last_lock_error", "") or "")

    def last_lock_failure_was_contention(self) -> bool:
        return bool(getattr(self, "_last_lock_contention", False))

    @wraps(provider_cls.acquire_lock)
    def acquire_lock(self, lock_data: dict) -> bool:
        self._last_lock_error = ""
        self._last_lock_contention = False
        logger.info("Atomic lock acquisition started: owner=%s", lock_data.get("owner"))

        try:
            expected_oid = self._remote_lock_oid()
            if expected_oid is not None:
                self._fetch_lock_branch()
                remote_lock = self._read_lock_from_oid(expected_oid)
                if self._is_lock_valid(remote_lock):
                    owner = remote_lock.get("owner") or remote_lock.get("username") or "unknown"
                    self._last_lock_contention = True
                    self._last_lock_error = f"Write lock is held by {owner}."
                    logger.info("Lock already held by %s, acquisition denied", owner)
                    return False

            lock_data["lease_expires_at"] = (
                datetime.now() + timedelta(seconds=self._lease_duration_seconds)
            ).isoformat()

            commit_sha = self._create_lock_commit_plumbing(lock_data, expected_oid)
            if not commit_sha:
                self._last_lock_error = (
                    "Unable to create the remote write-lock commit. "
                    "Check local Git repository health and commit identity."
                )
                logger.error(self._last_lock_error)
                return False

            if not self._push_lock_branch(commit_sha, expected_oid):
                # A failed CAS may be a legitimate race. Re-read authority before
                # classifying it as a Git/credential failure.
                current_oid = self._remote_lock_oid()
                if current_oid is not None:
                    current_lock = self._read_lock_from_oid(current_oid)
                    current_session = current_lock.get("session_id")
                    requested_session = lock_data.get("session_id")
                    if (
                        current_session
                        and current_session != requested_session
                        and self._is_lock_valid(current_lock)
                    ):
                        owner = current_lock.get("owner") or current_lock.get("username") or "another user"
                        self._last_lock_contention = True
                        self._last_lock_error = f"Write lock was acquired by {owner} during the request."
                        logger.info(self._last_lock_error)
                        return False

                self._last_lock_error = (
                    "Remote rejected the write-lock update. Check Git write permission, "
                    "credentials, network connectivity, and branch/ruleset policy."
                )
                logger.error(self._last_lock_error)
                return False

            new_oid = self._remote_lock_oid()
            if new_oid is None:
                self._last_lock_error = (
                    "Write-lock push completed but the remote lock reference disappeared during verification."
                )
                logger.error(self._last_lock_error)
                return False

            remote_verify = self._read_lock_from_oid(new_oid)
            if remote_verify.get("session_id") == lock_data.get("session_id"):
                logger.info(
                    "Atomic lock acquired successfully: session=%s",
                    lock_data.get("session_id"),
                )
                return True

            if self._is_lock_valid(remote_verify):
                owner = remote_verify.get("owner") or remote_verify.get("username") or "another user"
                self._last_lock_contention = True
                self._last_lock_error = f"Write lock ownership changed to {owner} during verification."
            else:
                self._last_lock_error = (
                    "Write-lock push succeeded but ownership verification failed. "
                    "The remote lock record could not be validated."
                )
            logger.error(self._last_lock_error)
            return False

        except Exception as exc:
            # The provider safety wrappers sanitize Git command output before it
            # reaches this layer. Still keep the user-facing prefix stable so UI
            # and diagnostics can distinguish an operational failure from contention.
            self._last_lock_error = f"Write-lock acquisition failed: {exc}"
            logger.exception(self._last_lock_error)
            return False

    provider_cls.acquire_lock = acquire_lock
    provider_cls.get_last_lock_error = get_last_lock_error
    provider_cls.last_lock_failure_was_contention = last_lock_failure_was_contention
    provider_cls._lock_acquisition_diagnostics_installed = True
