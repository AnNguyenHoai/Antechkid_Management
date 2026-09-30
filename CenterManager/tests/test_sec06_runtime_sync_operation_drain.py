import threading
import time

from centermanager.services.backup_operations_service import BackupOperationsService


class _FakeCollaborationManager:
    def __init__(self):
        self.guard = None
        self.guard_history = []

    def set_write_handoff_guard(self, guard):
        self.guard = guard
        self.guard_history.append(guard)


class _FakeRuntimeSyncService:
    def __init__(self):
        self._running = True
        self._thread = None
        self._poll_interval = 0.01
        self._status = "synchronizing"
        self.stop_called = False
        self.start_called = False

    def stop(self):
        self.stop_called = True
        self._running = False

    def start(self):
        self.start_called = True
        self._running = True

    def current_state(self):
        return {"status": self._status}

    def execute_write_handoff_sync(self):
        return True


def test_recovery_waits_for_cross_thread_sync_operation_to_finish():
    """Regression: stopping the worker must not outrun a poller-thread handoff sync."""
    manager = _FakeCollaborationManager()
    sync = _FakeRuntimeSyncService()
    service = BackupOperationsService(
        collaboration_manager=manager,
        runtime_sync_service=sync,
    )

    result = {}

    def pause():
        result["was_running"] = service._pause_runtime_sync_for_recovery()

    waiter = threading.Thread(target=pause)
    waiter.start()

    # The RuntimeSync worker is stopped immediately, but the independent
    # operation is still SYNCHRONIZING. Recovery must therefore still be waiting.
    deadline = time.monotonic() + 1.0
    while not sync.stop_called and time.monotonic() < deadline:
        time.sleep(0.005)
    assert sync.stop_called
    time.sleep(0.05)
    assert waiter.is_alive()

    # The collaboration handoff path is fail-closed while the drain is active.
    assert manager.guard is not None
    assert manager.guard() is False

    sync._status = "idle"
    waiter.join(timeout=1.0)

    assert not waiter.is_alive()
    assert result["was_running"] is True


def test_failed_recovery_can_restore_handoff_guard_and_runtime_sync():
    manager = _FakeCollaborationManager()
    sync = _FakeRuntimeSyncService()
    sync._status = "idle"
    service = BackupOperationsService(
        collaboration_manager=manager,
        runtime_sync_service=sync,
    )

    was_running = service._pause_runtime_sync_for_recovery()
    assert was_running is True
    assert manager.guard() is False

    service._resume_write_handoff_sync()
    sync.start()

    assert sync.start_called is True
    assert manager.guard == sync.execute_write_handoff_sync
    assert manager.guard() is True
