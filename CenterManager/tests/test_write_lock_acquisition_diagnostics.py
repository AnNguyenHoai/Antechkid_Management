"""Regression coverage for distributed WRITE acquisition diagnostics."""

from centermanager.platform.synchronization.lock_acquisition_diagnostics import (
    install_lock_acquisition_diagnostics,
)


class _BaseFakeProvider:
    _lease_duration_seconds = 60
    _lock_branch = "lock-main"

    def acquire_lock(self, lock_data):  # replaced by installer
        raise AssertionError("diagnostic wrapper was not installed")

    def _fetch_lock_branch(self):
        return True

    def _create_lock_commit_plumbing(self, lock_data, expected_oid=None):
        return "new-lock-commit"

    def _has_remote_origin(self):
        return True


class _ContendedProvider(_BaseFakeProvider):
    def _remote_lock_oid(self):
        return "remote-lock"

    def _read_lock_from_oid(self, oid):
        return {
            "locked": True,
            "owner": "alice",
            "session_id": "other-session",
            "lease_expires_at": "2999-01-01T00:00:00",
        }

    def _is_lock_valid(self, lock_data):
        return bool(lock_data.get("locked"))

    def _push_lock_branch(self, commit_sha, expected_oid=None):
        raise AssertionError("push must not run while another valid lease exists")

    def _run_git_command(self, args, check=True):
        raise AssertionError("git push must not run while another valid lease exists")


class _PushRejectedProvider(_BaseFakeProvider):
    def _remote_lock_oid(self):
        return None

    def _read_lock_from_oid(self, oid):
        return {}

    def _is_lock_valid(self, lock_data):
        return False

    def _push_lock_branch(self, commit_sha, expected_oid=None):
        return False

    def _run_git_command(self, args, check=True):
        assert args[:2] == ["push", "origin"]
        raise RuntimeError(
            "remote: permission denied to update refs/heads/lock-main\n"
            "error: failed to push some refs"
        )


class _NoOriginProvider(_PushRejectedProvider):
    def _has_remote_origin(self):
        return False

    def _run_git_command(self, args, check=True):
        raise AssertionError("git must not run without an origin")


def test_acquire_lock_classifies_real_remote_contention():
    install_lock_acquisition_diagnostics(_ContendedProvider)
    provider = _ContendedProvider()

    acquired = provider.acquire_lock(
        {"owner": "bob", "session_id": "current-session"}
    )

    assert acquired is False
    assert provider.last_lock_failure_was_contention() is True
    assert provider.get_last_lock_error() == "Write lock is held by alice."


def test_acquire_lock_preserves_exact_push_failure_when_remote_is_free():
    install_lock_acquisition_diagnostics(_PushRejectedProvider)
    provider = _PushRejectedProvider()

    acquired = provider.acquire_lock(
        {"owner": "bob", "session_id": "current-session"}
    )

    assert acquired is False
    assert provider.last_lock_failure_was_contention() is False
    message = provider.get_last_lock_error()
    assert message.startswith("Remote write-lock update failed:")
    assert "permission denied to update refs/heads/lock-main" in message
    assert "failed to push some refs" in message
    assert "\n" not in message


def test_acquire_lock_reports_missing_remote_origin():
    install_lock_acquisition_diagnostics(_NoOriginProvider)
    provider = _NoOriginProvider()

    acquired = provider.acquire_lock(
        {"owner": "bob", "session_id": "current-session"}
    )

    assert acquired is False
    assert provider.last_lock_failure_was_contention() is False
    assert (
        provider.get_last_lock_error()
        == "Remote write-lock update failed: No remote origin is configured for the write-lock repository."
    )
