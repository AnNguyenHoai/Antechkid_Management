# -*- coding: utf-8 -*-
"""Regression tests for WRITE handoff ordering and FIFO safety."""

from types import SimpleNamespace

from centermanager.services.write_transaction import (
    WriteTransactionManager,
    WriteTransactionState,
)
from centermanager.platform.collaboration import CollaborationManager
from centermanager.events.event_bus import EventBus


def test_publish_completes_before_lock_release():
    """A writer must be PUBLISHED before its lock is released for handoff."""
    order = []

    class FakeLock:
        def clear_finishing_data(self):
            order.append("clear_finishing")

    class FakeCollaboration:
        def __init__(self):
            self._lock = FakeLock()

        def is_writing(self):
            return True

        def release_write(self):
            order.append("release")
            return True

    collab = FakeCollaboration()
    manager = WriteTransactionManager(collab)
    manager._state = WriteTransactionState.LOCAL_SAVED
    manager._do_publish = lambda: order.append("publish") or True

    def on_success():
        order.append("success_callback")
        assert manager.state == WriteTransactionState.PUBLISHED

    manager._on_publish_success = on_success

    assert manager._publish() is True

    assert order == [
        "publish",
        "success_callback",
        "clear_finishing",
        "release",
    ]

    assert order.index("publish") < order.index("release")
    assert manager.state == WriteTransactionState.IDLE

def test_queue_head_is_required_before_waiting_writer_can_grant(tmp_path):
    """Only the queue head may acquire after the current writer releases."""
    runtime_root = tmp_path / "runtime"
    event_bus = EventBus()

    cm_a = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_a.initialize("user_a", "User A", "admin")
    assert cm_a.request_write().is_granted

    cm_b = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_b.initialize("user_b", "User B", "admin")
    assert cm_b.request_write().is_waiting

    cm_c = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_c.initialize("user_c", "User C", "admin")
    assert cm_c.request_write().is_waiting

    cm_a.release_write()

    assert cm_c.grant_existing_waiting_request() is False
    assert not cm_c.is_writing()
    assert cm_b.grant_existing_waiting_request() is True
    assert cm_b.is_writing()

    cm_b.release_write()
    assert cm_c.grant_existing_waiting_request() is True
    assert cm_c.is_writing()

    cm_c.release_write()
    cm_a.shutdown()
    cm_b.shutdown()
    cm_c.shutdown()
