import inspect

import pytest

from centermanager.services.backup_operations_service import (
    BackupOperationsService,
    BackupRestoreAuthorizationError,
)


class _DrainableThread:
    def __init__(self, events):
        self._alive = True
        self._events = events

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        self._events.append(("join", timeout))
        self._alive = False


class _StuckThread(_DrainableThread):
    def join(self, timeout=None):
        self._events.append(("join", timeout))


class _RuntimeSync:
    def __init__(self, thread, events, *, running=True, poll_interval=30):
        self._thread = thread
        self._events = events
        self._running = running
        self._poll_interval = poll_interval

    def stop(self):
        self._events.append(("stop", None))
        self._running = False

    def start(self):
        self._events.append(("start", None))
        self._running = True


def test_recovery_drains_background_sync_worker_before_destructive_path():
    events = []
    thread = _DrainableThread(events)
    sync = _RuntimeSync(thread, events, poll_interval=30)
    service = BackupOperationsService(backup_service=object(), runtime_sync_service=sync)

    assert service._pause_runtime_sync_for_recovery() is True
    assert events[0] == ("stop", None)
    assert events[1][0] == "join"
    assert events[1][1] >= 35.0
    assert thread.is_alive() is False


def test_recovery_fails_closed_if_background_sync_cannot_be_drained():
    events = []
    thread = _StuckThread(events)
    sync = _RuntimeSync(thread, events, poll_interval=1)
    service = BackupOperationsService(backup_service=object(), runtime_sync_service=sync)

    with pytest.raises(
        BackupRestoreAuthorizationError,
        match="Background synchronization did not quiesce",
    ):
        service._pause_runtime_sync_for_recovery()

    assert events[0] == ("stop", None)
    assert events[1][0] == "join"


def test_restore_quiesces_sync_before_safety_backup_and_live_restore():
    source = inspect.getsource(BackupOperationsService.restore_backup)

    pause_at = source.index("_pause_runtime_sync_for_recovery()")
    safety_at = source.index('create_backup(label="pre_restore")')
    restore_at = source.index("self._backup.restore_backup(")

    assert pause_at < safety_at < restore_at
