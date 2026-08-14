# -*- coding: utf-8 -*-
"""Tests for collaboration waiting user visibility."""

import pytest
import time
from pathlib import Path

from centermanager.platform.collaboration import CollaborationManager
from centermanager.events.event_bus import EventBus


@pytest.fixture
def temp_collab(tmp_path):
    """Create collaboration manager with temp runtime."""
    event_bus = EventBus()
    cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)
    cm.initialize("user_a", "User A", "admin")
    return cm


def test_get_waiting_users_empty(temp_collab):
    """No waiting users when queue empty."""
    waiting = temp_collab.get_waiting_users()
    assert waiting == []


def test_get_waiting_users_after_request(temp_collab):
    """Waiting users appear after request."""
    temp_collab.request_write()

    cm_b = CollaborationManager(
        runtime_root=temp_collab._runtime_root,
        event_bus=EventBus()
    )
    cm_b.initialize("user_b", "User B", "teacher")
    cm_b.request_write()
    time.sleep(0.5)

    waiting = temp_collab.get_waiting_users()
    assert len(waiting) >= 1
    assert any(w["username"] == "User B" for w in waiting)


def test_waiting_users_after_release(temp_collab):
    """Waiting list clears after writer releases and next auto-acquires."""
    # A acquires lock
    temp_collab.request_write()
    assert temp_collab.is_writing() is True

    # B requests (enters queue)
    cm_b = CollaborationManager(
        runtime_root=temp_collab._runtime_root,
        event_bus=EventBus()
    )
    cm_b.initialize("user_b", "User B", "teacher")
    cm_b.request_write()
    time.sleep(0.5)

    # Verify B is waiting
    waiting = temp_collab.get_waiting_users()
    assert len(waiting) >= 1
    assert any(w["username"] == "User B" for w in waiting)

    # A releases lock
    temp_collab.release_write()
    time.sleep(1.0)

    # B should auto-acquire via is_next_eligible polling
    # We need to simulate the polling by calling request_write again
    # or calling is_next_eligible to trigger auto-acquire.
    # In real UI, _update_waiting_status would trigger it.
    # For test, we simulate:
    if cm_b.is_next_eligible():
        cm_b.request_write()

    time.sleep(0.5)

    # B should now be writing
    assert cm_b.is_writing() is True

    # A checks waiting list - B should not be in waiting list
    waiting = temp_collab.get_waiting_users()
    assert all(w["username"] != "User B" for w in waiting)


def test_get_waiting_users_multiple(temp_collab):
    """Multiple waiting users appear correctly."""
    temp_collab.request_write()

    cm_b = CollaborationManager(
        runtime_root=temp_collab._runtime_root,
        event_bus=EventBus()
    )
    cm_b.initialize("user_b", "User B", "teacher")
    cm_b.request_write()

    cm_c = CollaborationManager(
        runtime_root=temp_collab._runtime_root,
        event_bus=EventBus()
    )
    cm_c.initialize("user_c", "User C", "teacher")
    cm_c.request_write()

    time.sleep(0.5)

    waiting = temp_collab.get_waiting_users()
    assert len(waiting) >= 2
    usernames = [w["username"] for w in waiting]
    assert "User B" in usernames
    assert "User C" in usernames