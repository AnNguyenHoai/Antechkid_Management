# -*- coding: utf-8 -*-
"""3.3.5-B.1 deterministic three-client FIFO contention regression."""

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager


def test_three_client_fifo_handoff(tmp_path):
    """The first waiter must acquire before the second waiter, then the second may acquire."""
    runtime_root = tmp_path / "runtime"
    event_bus = EventBus()

    clients = []
    try:
        cm_a = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
        cm_b = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
        cm_c = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
        clients = [cm_a, cm_b, cm_c]

        cm_a.initialize("user_a", "User A", "admin")
        cm_b.initialize("user_b", "User B", "admin")
        cm_c.initialize("user_c", "User C", "admin")

        # A is the current writer; B and C establish a deterministic FIFO queue.
        assert cm_a.request_write().is_granted
        b_wait = cm_b.request_write()
        c_wait = cm_c.request_write()
        assert b_wait.is_waiting
        assert c_wait.is_waiting

        queue = cm_a.get_queue()
        request_ids = [item["request_id"] for item in queue["requests"]]
        assert request_ids == [b_wait.request_id, c_wait.request_id]
        assert queue["next"]["request_id"] == b_wait.request_id
        assert cm_a.get_queue_length() == 2

        # Releasing A must not allow C to bypass B.
        assert cm_a.release_write()
        assert cm_c.grant_existing_waiting_request(c_wait.request_id) is False
        assert not cm_c.is_writing()
        assert cm_b.grant_existing_waiting_request(b_wait.request_id) is True
        assert cm_b.is_writing()
        assert not cm_c.is_writing()

        queue_after_b = cm_b.get_queue()
        remaining_ids = [item["request_id"] for item in queue_after_b["requests"]]
        assert remaining_ids == [c_wait.request_id]
        assert queue_after_b["next"]["request_id"] == c_wait.request_id

        # After B releases, C becomes the head and can acquire.
        assert cm_b.release_write()
        assert cm_c.grant_existing_waiting_request(c_wait.request_id) is True
        assert cm_c.is_writing()
        assert not cm_a.is_writing()
        assert not cm_b.is_writing()
        assert cm_c.get_queue_length() == 0
    finally:
        for client in reversed(clients):
            try:
                client.shutdown()
            except Exception:
                pass
