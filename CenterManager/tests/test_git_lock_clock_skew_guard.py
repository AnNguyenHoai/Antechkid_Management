# -*- coding: utf-8 -*-
"""Regression tests for distributed WRITE-lock clock-skew protection."""

from datetime import datetime, timedelta

from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.platform.synchronization.git_clock_skew_guard import (
    DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS,
    is_remote_write_lock_reclaimable,
)


def _lock_with_expiry(
    expires_at: datetime,
    *,
    locked: bool = True,
    session_id: str = "session-a",
) -> dict:
    return {
        "locked": locked,
        "owner": "machine-a",
        "session_id": session_id,
        "lease_expires_at": expires_at.isoformat(),
    }


def _contender(session_id: str = "session-b") -> dict:
    return {
        "locked": True,
        "owner": "machine-b",
        "session_id": session_id,
    }


def test_expired_lease_remains_strictly_invalid_inside_clock_skew_window(tmp_path):
    """Clock-skew policy must never redefine generic lock validity."""
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")
    apparent_expiry = datetime.now() - timedelta(minutes=7)

    assert DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS >= 7 * 60
    assert provider._is_lock_valid(_lock_with_expiry(apparent_expiry)) is False


def test_other_runtime_cannot_reclaim_expired_write_lock_inside_skew_window():
    now = datetime.now()
    remote_lock = _lock_with_expiry(now - timedelta(minutes=7))

    assert (
        is_remote_write_lock_reclaimable(remote_lock, _contender(), now=now)
        is False
    )


def test_other_runtime_can_reclaim_write_lock_after_skew_window():
    now = datetime.now()
    remote_lock = _lock_with_expiry(
        now - timedelta(seconds=DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS + 5)
    )

    assert (
        is_remote_write_lock_reclaimable(remote_lock, _contender(), now=now)
        is True
    )


def test_same_session_can_reclaim_its_expired_write_lock_immediately():
    now = datetime.now()
    remote_lock = _lock_with_expiry(
        now - timedelta(seconds=1),
        session_id="same-session",
    )

    assert (
        is_remote_write_lock_reclaimable(
            remote_lock,
            _contender(session_id="same-session"),
            now=now,
        )
        is True
    )


def test_live_write_lock_is_never_reclaimable_even_by_same_session():
    now = datetime.now()
    remote_lock = _lock_with_expiry(
        now + timedelta(seconds=30),
        session_id="same-session",
    )

    assert (
        is_remote_write_lock_reclaimable(
            remote_lock,
            _contender(session_id="same-session"),
            now=now,
        )
        is False
    )


def test_unlocked_remote_state_is_reclaimable_without_skew_delay():
    now = datetime.now()
    remote_lock = _lock_with_expiry(
        now - timedelta(minutes=1),
        locked=False,
    )

    assert is_remote_write_lock_reclaimable(remote_lock, _contender(), now=now) is True


def test_malformed_lease_keeps_historical_stale_lock_behavior():
    remote_lock = {
        "locked": True,
        "owner": "machine-a",
        "session_id": "session-a",
        "lease_expires_at": "not-a-timestamp",
    }

    assert is_remote_write_lock_reclaimable(remote_lock, _contender()) is True


def test_acquire_denies_other_runtime_inside_skew_window_without_creating_commit(
    tmp_path,
    monkeypatch,
):
    """Guard must sit in the actual acquire/reclaim path, not validity primitive."""
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")
    remote_lock = _lock_with_expiry(datetime.now() - timedelta(minutes=7))
    create_called = False

    monkeypatch.setattr(provider, "_remote_lock_oid", lambda: "remote-oid")
    monkeypatch.setattr(provider, "_fetch_lock_branch", lambda: True)
    monkeypatch.setattr(provider, "_read_lock_from_oid", lambda _oid: remote_lock)

    def _unexpected_create(*_args, **_kwargs):
        nonlocal create_called
        create_called = True
        return "new-commit"

    monkeypatch.setattr(provider, "_create_lock_commit_plumbing", _unexpected_create)

    assert provider.acquire_lock(_contender()) is False
    assert create_called is False
    assert provider._is_lock_valid(remote_lock) is False


def test_provider_exposes_installed_clock_skew_policy(tmp_path):
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")

    assert provider._clock_skew_guard_installed is True
    assert (
        provider._clock_skew_tolerance_seconds
        == DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS
    )
