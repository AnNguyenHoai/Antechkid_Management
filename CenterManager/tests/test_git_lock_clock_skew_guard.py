# -*- coding: utf-8 -*-
"""Regression tests for distributed write-lock clock-skew protection."""

from datetime import datetime, timedelta

from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.platform.synchronization.git_clock_skew_guard import (
    DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS,
)


def _lock_with_expiry(expires_at: datetime, *, locked: bool = True) -> dict:
    return {
        "locked": locked,
        "owner": "machine-a",
        "session_id": "session-a",
        "lease_expires_at": expires_at.isoformat(),
    }


def test_recently_expired_remote_lock_remains_valid_inside_clock_skew_window(tmp_path):
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")

    # Reproduce the audited failure mode: machine B is about seven minutes
    # ahead of machine A, so A's fresh lease looks expired on B immediately.
    apparent_expiry = datetime.now() - timedelta(minutes=7)

    assert DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS >= 7 * 60
    assert provider._is_lock_valid(_lock_with_expiry(apparent_expiry)) is True


def test_remote_lock_becomes_stale_after_clock_skew_window(tmp_path):
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")

    expired_beyond_guard = datetime.now() - timedelta(
        seconds=DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS + 5
    )

    assert provider._is_lock_valid(_lock_with_expiry(expired_beyond_guard)) is False


def test_unlocked_remote_state_is_never_revived_by_clock_skew_guard(tmp_path):
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")

    apparent_expiry = datetime.now() - timedelta(minutes=1)

    assert provider._is_lock_valid(
        _lock_with_expiry(apparent_expiry, locked=False)
    ) is False


def test_malformed_lease_remains_stale(tmp_path):
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")

    lock_data = {
        "locked": True,
        "owner": "machine-a",
        "session_id": "session-a",
        "lease_expires_at": "not-a-timestamp",
    }

    assert provider._is_lock_valid(lock_data) is False


def test_provider_exposes_installed_clock_skew_policy(tmp_path):
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")

    assert provider._clock_skew_guard_installed is True
    assert (
        provider._clock_skew_tolerance_seconds
        == DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS
    )
