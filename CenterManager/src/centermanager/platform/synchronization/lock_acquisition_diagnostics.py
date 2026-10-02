"""Write-lock acquisition diagnostics for GitSynchronizationProvider.

This compatibility layer keeps the existing provider implementation intact while
making lock-acquisition failures observable. A failed acquisition is classified
as either real contention (another authoritative remote lease exists) or an
operational failure such as commit creation, push rejection, or ownership
verification.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def _clean_diagnostic(value: object, limit: int = 700) -> str:
    """Keep a compact, already-sanitized diagnostic suitable for logs and UI."""
    text = " ".join(str(value or "").split()).strip()
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _remote_lock_blocks_reclaim(self, remote_lock: dict, contender_lock: dict) -> bool:
    """Return whether an invalid remote lock is still protected from takeover.

    Generic lease validity remains strict. Optional collaboration policies such
    as the bounded clock-skew guard are consulted only for stale-lock reclaim.
    When no policy is installed, historical behavior is preserved and an expired
    lock is immediately reclaimable.
    """
    policy = getattr(self, "_is_remote_write_lock_reclaimable", None)
    if not callable(policy):
        return False
    return not bool(policy(remote_lock, contender_lock))


def install_lock_acquisition_diagnostics(provider_cls) -> None:
    """Install precise lock-acquisition failure reporting once."""
    if getattr(provider_cls, "_lock_acquisition_diagnostics_installed", False):
        return

    def get_last_lock_error(self) -> str:
        return str(getattr(self, "_last_lock_error", "") or "")

    def last_lock_failure_was_contention(self) -> bool:
        return bool(getattr(self, "_last_lock_contention", False))

    # The restored provider's _push_lock_branch() deliberately returned only a
    # bool and swallowed the Git exception. Capture the exception here, after
    # git output/credential safety wrappers are installed, so the acquisition
    # layer can surface the real sanitized remote failure instead of guessing.
    original_push = getattr(provider_cls, "_push_lock_branch", None)

    if callable(original_push):
        @wraps(original_push)
        def push_lock_branch(self, commit_sha: str, expected_oid=None) -> bool:
            self._last_lock_push_error = ""

            if not self._has_remote_origin():
                self._last_lock_push_error = "No remote origin is configured for the write-lock repository."
                logger.error(self._last_lock_push_error)
                return False

            if expected_oid is None:
                args = ["push", "origin", f"{commit_sha}:refs/heads/{self._lock_branch}"]
            else:
                args = ["push", "origin", f"{commit_sha}:refs/heads/{self._lock_branch}"]
                args.append(f"--force-with-lease={self._lock_branch}:{expected_oid}")

            try:
                self._run_git_command(args, check=True)
                logger.info("Lock branch pushed successfully: %s", self._lock_branch)
                return True
            except Exception as exc:
                detail = _clean_diagnostic(exc) or exc.__class__.__name__
                self._last_lock_push_error = detail
                logger.error("Lock branch push failed: %s", detail)
                return False

        provider_cls._push_lock_branch = push_lock_branch

    @wraps(provider_cls.acquire_lock)
    def acquire_lock(self, lock_data: dict) -> bool:
        self._last_lock_error = ""
        self._last_lock_contention = False
        self._last_lock_push_error = ""
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

                # An expired lease is strictly invalid, but a separate reclaim
                # policy may still protect another runtime's WRITE lock for a
                # bounded clock-skew grace interval.
                if _remote_lock_blocks_reclaim(self, remote_lock, lock_data):
                    owner = remote_lock.get("owner") or remote_lock.get("username") or "unknown"
                    self._last_lock_contention = True
                    self._last_lock_error = (
                        f"Write lock held by {owner} is inside the clock-skew "
                        "safety window."
                    )
                    logger.info("%s Acquisition denied.", self._last_lock_error)
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
                # A failed CAS may still be a legitimate race. Re-read the
                # authoritative lock before classifying it as an operational
                # Git failure.
                current_oid = self._remote_lock_oid()
                if current_oid is not None:
                    current_lock = self._read_lock_from_oid(current_oid)
                    current_session = current_lock.get("session_id")
                    requested_session = lock_data.get("session_id")
                    current_blocks_takeover = self._is_lock_valid(current_lock)
                    if not current_blocks_takeover:
                        current_blocks_takeover = _remote_lock_blocks_reclaim(
                            self,
                            current_lock,
                            lock_data,
                        )

                    if (
                        current_session
                        and current_session != requested_session
                        and current_blocks_takeover
                    ):
                        owner = current_lock.get("owner") or current_lock.get("username") or "another user"
                        self._last_lock_contention = True
                        self._last_lock_error = f"Write lock was acquired by {owner} during the request."
                        logger.info(self._last_lock_error)
                        return False

                push_detail = _clean_diagnostic(
                    getattr(self, "_last_lock_push_error", "")
                )
                if push_detail:
                    self._last_lock_error = (
                        f"Remote write-lock update failed: {push_detail}"
                    )
                else:
                    self._last_lock_error = (
                        "Remote write-lock update failed without an active competing writer. "
                        "No Git diagnostic was returned."
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

            if self._is_lock_valid(remote_verify) or _remote_lock_blocks_reclaim(
                self,
                remote_verify,
                lock_data,
            ):
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
            # reaches this layer. Keep the failure concise but preserve the root
            # exception so support logs and UI expose the actionable cause.
            detail = _clean_diagnostic(exc) or exc.__class__.__name__
            self._last_lock_error = f"Write-lock acquisition failed: {detail}"
            logger.exception(self._last_lock_error)
            return False

    provider_cls.acquire_lock = acquire_lock
    provider_cls.get_last_lock_error = get_last_lock_error
    provider_cls.last_lock_failure_was_contention = last_lock_failure_was_contention
    provider_cls._lock_acquisition_diagnostics_installed = True
