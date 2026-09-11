# -*- coding: utf-8 -*-
"""TASK 3.3.4-B.1 — active editing remote lease renewal."""

from datetime import datetime, timedelta
import importlib.util

import pytest

from centermanager.platform.collaboration import CollaborationManager, CollaborationPoller


class FakeRemoteProvider:
    def __init__(self, owner="user_a", session_id="session_a", remaining=10):
        self.owner = owner
        self.session_id = session_id
        self.remaining = remaining
        self.renew_calls = []
        self.renewed = True

    def remote_lock_status(self):
        return {
            "locked": True,
            "owner": self.owner,
            "session_id": self.session_id,
            "lease_expires_at": (
                datetime.now() + timedelta(seconds=self.remaining)
            ).isoformat(),
            "user_id": self.owner,
            "machine": "test-machine",
        }

    def renew_lock(self, owner, session_id):
        self.renew_calls.append((owner, session_id))
        return self.renewed


@pytest.fixture
def manager(tmp_path):
    provider = FakeRemoteProvider()
    cm = CollaborationManager(
        runtime_root=tmp_path,
        sync_provider=provider,
        lock_timeout=60,
    )
    cm.initialize("user_a", "user_a", "admin")
    # The remote lock must belong to this exact collaboration session.
    # renew_remote_lease() intentionally fences stale/foreign sessions.
    provider.session_id = cm.get_session().session_id
    cm._is_writing = True
    cm._lock_acquired = True
    return cm, provider


def test_active_writer_renews_when_lease_near_expiry(manager):
    cm, provider = manager

    assert cm.renew_remote_lease() is True
    assert provider.renew_calls == [("user_a", cm.get_session().session_id)]


def test_active_writer_does_not_renew_healthy_lease(manager):
    cm, provider = manager
    provider.remaining = 50

    assert cm.renew_remote_lease() is True
    assert provider.renew_calls == []


def test_renewal_requires_current_session_ownership(manager):
    cm, provider = manager
    provider.session_id = "other-session"

    assert cm.renew_remote_lease() is False
    assert provider.renew_calls == []


def test_renewal_failure_does_not_mutate_writer_state(manager):
    cm, provider = manager
    provider.renewed = False

    assert cm.renew_remote_lease() is False
    assert cm.is_writing() is True
    assert cm._lock_acquired is True


def test_force_renewal_renews_even_with_healthy_lease(manager):
    cm, provider = manager
    provider.remaining = 50

    assert cm.renew_remote_lease(force=True) is True
    assert provider.renew_calls == [("user_a", cm.get_session().session_id)]


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 required for poller lifecycle",
)
def test_poller_owns_independent_lease_timer(tmp_path):
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    app = QCoreApplication.instance() or QCoreApplication([])
    provider = FakeRemoteProvider(remaining=10)
    cm = CollaborationManager(
        runtime_root=tmp_path,
        sync_provider=provider,
        lock_timeout=60,
    )
    cm.initialize("user_a", "user_a", "admin")
    # Match the fake remote lock to the active local session so the test
    # exercises the timer, not ownership fencing.
    provider.session_id = cm.get_session().session_id
    cm._is_writing = True
    cm._lock_acquired = True

    poller = CollaborationPoller(
        cm,
        normal_interval=60,
        waiting_interval=60,
        lease_renewal_interval=1,
    )

    try:
        poller.start(initial_poll=False)
        deadline = datetime.now() + timedelta(seconds=3)
        while datetime.now() < deadline and not provider.renew_calls:
            app.processEvents()
            QTimer.singleShot(20, lambda: None)
        assert provider.renew_calls
    finally:
        poller.stop()
