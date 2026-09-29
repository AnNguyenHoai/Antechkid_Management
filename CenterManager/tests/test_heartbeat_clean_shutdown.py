import threading
import time

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import (
    CollaborationManager,
    HeartbeatManager,
    HeartbeatRepository,
    RuntimeSession,
)


def test_heartbeat_stop_interrupts_long_interval_and_joins(tmp_path):
    repo = HeartbeatRepository(tmp_path / "heartbeat")
    session = RuntimeSession(user_id="u1", username="tester", role="admin")
    manager = HeartbeatManager(repo, session, interval_seconds=60)

    manager.start()
    thread = manager._thread
    assert thread is not None
    assert thread.is_alive()

    started = time.monotonic()
    manager.stop()
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert not thread.is_alive()
    assert manager._thread is None


def test_collaboration_shutdown_does_not_leave_heartbeat_thread(tmp_path):
    cm = CollaborationManager(
        runtime_root=tmp_path,
        event_bus=EventBus(),
        heartbeat_interval=60,
    )
    cm.initialize("u1", "tester", "admin")

    thread = cm._heartbeat_manager._thread
    assert thread is not None and thread.is_alive()

    cm.shutdown()

    assert not thread.is_alive()
    assert not any(
        candidate is thread and candidate.is_alive()
        for candidate in threading.enumerate()
    )


def test_repeated_collaboration_lifecycle_does_not_accumulate_heartbeat_threads(tmp_path):
    baseline = {
        thread.ident
        for thread in threading.enumerate()
        if thread.name.startswith("heartbeat-") and thread.is_alive()
    }

    for index in range(12):
        cm = CollaborationManager(
            runtime_root=tmp_path / f"runtime-{index}",
            event_bus=EventBus(),
            heartbeat_interval=60,
        )
        cm.initialize(str(index), f"user-{index}", "admin")
        cm.shutdown()

    leaked = [
        thread
        for thread in threading.enumerate()
        if thread.name.startswith("heartbeat-")
        and thread.is_alive()
        and thread.ident not in baseline
    ]
    assert leaked == []
