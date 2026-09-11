"""Regression tests for automatic waiting-request handoff ordering."""

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.collaboration.events import WriteGranted


def test_write_granted_is_published_before_waiting_request_is_consumed(tmp_path):
    """A waiting transaction must observe its grant before its queue file disappears."""
    runtime_root = tmp_path / "runtime"
    event_bus = EventBus()

    cm_a = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_b = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_a.initialize("user_a", "User A", "admin")
    cm_b.initialize("user_b", "User B", "admin")

    assert cm_a.request_write().is_granted
    waiting = cm_b.request_write()
    assert waiting.is_waiting

    observed = []

    def on_granted(event):
        if event.session_id == cm_b.get_session_id():
            observed.append(cm_b.has_pending_waiting_request(event.request_id))

    event_bus.register(WriteGranted, on_granted)

    cm_a.release_write()
    assert cm_b.grant_existing_waiting_request(waiting.request_id)

    assert observed == [True]
    assert not cm_b.has_pending_waiting_request(waiting.request_id)
    assert cm_b.is_writing()

    cm_b.release_write()
    cm_a.shutdown()
    cm_b.shutdown()
