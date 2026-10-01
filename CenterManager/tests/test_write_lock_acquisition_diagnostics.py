"""Regression coverage for distributed WRITE acquisition diagnostics."""

from centermanager.platform.synchronization.lock_acquisition_diagnostics import (
    install_lock_acquisition_diagnostics,
)


class _BaseFakeProvider:
    _lease_duration_seconds = 60

    def acquire_lock(self, lock_data):  # replaced by installer
        raise AssertionError("diagnostic wrapper was not installed")

    def _fetch_lock_branch(self):
        return True

    def _create_lock_commit_plumbing(self, lock_data, expected_oid=None):
        return "new-lock-commit"


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


class _PushRejectedProvider(_BaseFakeProvider):
    def _remote_lock_oid(self):
        return None

    def _read_lock_from_oid(self, oid):
        return {}

    def _is_lock_valid(self, lock_data):
        return False

    def _push_lock_branch(self, commit_sha, expected_oid=None):
        return False


def test_acquire_lock_classifies_real_remote_contention():
    install_lock_acquisition_diagnostics(_ContendedProvider)
    provider = _ContendedProvider()

    acquired = provider.acquire_lock(
        {"owner": "bob", "session_id": "current-session"}
    )

    assert acquired is False
    assert provider.last_lock_failure_was_contention() is True
    assert provider.get_last_lock_error() == "Write lock is held by alice."


def test_acquire_lock_preserves_push_failure_when_remote_is_free():
    install_lock_acquisition_diagnostics(_PushRejectedProvider)
    provider = _PushRejectedProvider()

    acquired = provider.acquire_lock(
        {"owner": "bob", "session_id": "current-session"}
    )

    assert acquired is False
    assert provider.last_lock_failure_was_contention() is False
    message = provider.get_last_lock_error()
    assert "Remote rejected the write-lock update" in message
    assert "Git write permission" in message
