# -*- coding: utf-8 -*-
"""Regression coverage for remote FINISHING deadline authority."""

from datetime import datetime, timedelta

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager


class _RemoteLockProvider:
    """Minimal remote authority provider for deterministic validation tests."""

    def __init__(self):
        self.status = {}

    def health(self):
        return True

    def remote_lock_status(self):
        return dict(self.status)

    def release_lock(self, username):
        """Release the test-owned remote lock, matching the manager contract."""
        if self.status.get("owner") == username or self.status.get("username") == username:
            self.status = {}
        return True


def _manager(tmp_path, provider):
    manager = CollaborationManager(
        runtime_root=tmp_path,
        event_bus=EventBus(),
        sync_provider=provider,
    )
    manager.initialize("user_a", "User A", "admin")
    return manager


def test_remote_expired_finishing_deadline_invalid_even_with_live_lease(tmp_path):
    provider = _RemoteLockProvider()
    manager = _manager(tmp_path, provider)
    try:
        session = manager.get_session()
        now = datetime.now()
        provider.status = {
            "locked": True,
            "session_id": session.session_id,
            "owner": session.username,
            "username": session.username,
            "user_id": session.user_id,
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "finishing_started_at": (now - timedelta(seconds=130)).isoformat(),
            "finishing_deadline": (now - timedelta(seconds=10)).isoformat(),
            "publish_intent": True,
            "lock_generation": 0,
            "lease_revision": 0,
            "machine": "test_machine",
        }

        authority = manager.validate_write_authority(session)

        assert authority["valid"] is False
        assert authority["finishing_deadline"] == datetime.fromisoformat(
            provider.status["finishing_deadline"]
        )
        assert "deadline expired" in authority["reason"].lower()
    finally:
        manager.shutdown()


def test_remote_active_finishing_deadline_is_exposed_and_authoritative(tmp_path):
    provider = _RemoteLockProvider()
    manager = _manager(tmp_path, provider)
    try:
        session = manager.get_session()
        now = datetime.now()
        deadline = now + timedelta(seconds=120)
        provider.status = {
            "locked": True,
            "session_id": session.session_id,
            "owner": session.username,
            "username": session.username,
            "user_id": session.user_id,
            "acquired_at": now.isoformat(),
            "last_heartbeat": (now - timedelta(seconds=120)).isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "finishing_started_at": (now - timedelta(seconds=1)).isoformat(),
            "finishing_deadline": deadline.isoformat(),
            "publish_intent": True,
            "lock_generation": 0,
            "lease_revision": 0,
            "machine": "test_machine",
        }

        authority = manager.validate_write_authority(session)

        assert authority["valid"] is True
        assert authority["finishing_deadline"] == deadline
    finally:
        manager.shutdown()
