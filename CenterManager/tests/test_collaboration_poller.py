# -*- coding: utf-8 -*-
"""Deterministic core tests for CollaborationPoller."""

import threading
from unittest.mock import patch

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtTest import QSignalSpy

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager, CollaborationPoller


def wait_for_spy(spy: QSignalSpy, timeout_ms: int = 5000) -> bool:
    """Wait for a signal while explicitly pumping the Qt event loop.

    QSignalSpy.wait() is not used here because the signal originates from the
    poller QThread. The same event-loop polling strategy used by the passing
    single-flight test is deterministic for this cross-thread observation.
    """
    return wait_for_condition(lambda: spy.count() > 0, timeout_ms)


def wait_for_condition(predicate, timeout_ms: int = 5000, step_ms: int = 20) -> bool:
    """Bounded Qt event-loop wait; no wall-clock sleep."""
    loop = QEventLoop()
    result = {"ok": False}

    def check():
        if predicate():
            result["ok"] = True
            loop.quit()

    timer = QTimer()
    timer.setInterval(step_ms)
    timer.timeout.connect(check)
    timer.start()
    QTimer.singleShot(timeout_ms, loop.quit)
    check()
    loop.exec()
    timer.stop()
    return result["ok"]


def stop_poller(poller):
    """Always perform cooperative cleanup."""
    try:
        if poller is not None:
            poller.stop()
    finally:
        if poller is not None:
            assert not poller._thread.isRunning()


@pytest.fixture(scope="function")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    yield app
    app.processEvents()


class BlockingReader:
    def __init__(self, state=None):
        self.started = threading.Event()
        self.release = threading.Event()
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.state = state or {"locked": False}

    def get_state(self):
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        self.started.set()
        try:
            if not self.release.wait(timeout=5):
                raise RuntimeError("BlockingReader release timeout")
            return dict(self.state)
        finally:
            with self._lock:
                self.active -= 1


def make_poller(tmp_path):
    event_bus = EventBus()
    cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)
    cm.initialize("test_user", "test_user", "admin")
    return CollaborationPoller(cm, event_bus), cm


def test_timer_affinity(qapp, tmp_path):
    poller, _ = make_poller(tmp_path)
    try:
        poller.start(initial_poll=False)
        assert wait_for_condition(lambda: poller._timer is not None)
        assert poller._timer.thread() == poller._thread
    finally:
        stop_poller(poller)


def test_cross_thread_refresh(qapp, tmp_path):
    poller, cm = make_poller(tmp_path)
    try:
        spy = QSignalSpy(poller.poll_completed)
        poller.start(initial_poll=False)

        # The first poll is caused only by request_refresh(), so there is no
        # race with the historical automatic initial poll.
        poller.request_refresh("test")
        assert wait_for_spy(spy), "Refresh did not produce a completed poll"
        assert spy.count() == 1

        with patch.object(
            cm, "get_lock_status",
            return_value={"locked": True, "owner": "test", "session_id": "s1"},
        ):
            poller.request_refresh("state-change")
            assert wait_for_condition(lambda: spy.count() >= 2)
            assert poller.get_last_snapshot().remote_lock["owner"] == "test"
    finally:
        stop_poller(poller)


def test_stop_lifecycle(qapp, tmp_path):
    poller, _ = make_poller(tmp_path)
    try:
        poller.start(initial_poll=False)
        assert wait_for_condition(lambda: poller._timer is not None)
    finally:
        stop_poller(poller)
    assert not poller._thread.isRunning()


def test_single_flight_and_coalescing(qapp, tmp_path):
    poller, cm = make_poller(tmp_path)
    reader = BlockingReader()
    completed = QSignalSpy(poller.poll_completed)

    try:
        with patch.object(cm, "get_lock_status", side_effect=reader.get_state):
            poller.start(initial_poll=False)

            poller.request_refresh("first")
            assert reader.started.wait(3000), "First poll did not start"

            for _ in range(10):
                poller.request_refresh("coalesced")

            # Release the active poll. The poller must coalesce the ten
            # requests into one follow-up poll, not run them concurrently.
            reader.release.set()

            assert wait_for_condition(lambda: completed.count() >= 2, 5000)
            assert reader.max_active == 1
            assert completed.count() == 2
    finally:
        reader.release.set()
        stop_poller(poller)


def test_backoff_state_machine(qapp, tmp_path):
    # Use an explicit 1-second initial backoff so the expected exponential
    # sequence is deterministic: 1 -> 2 -> 4 -> 8 -> reset.
    event_bus = EventBus()
    cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)
    cm.initialize("test_user", "test_user", "admin")
    poller = CollaborationPoller(
        cm,
        event_bus,
        initial_backoff=1,
        max_backoff=10,
    )
    calls = {"count": 0}

    def fail_then_succeed():
        calls["count"] += 1
        if calls["count"] <= 3:
            raise RuntimeError(f"failure-{calls['count']}")
        return {"locked": False}

    completed = QSignalSpy(poller.poll_completed)

    try:
        with patch.object(cm, "get_lock_status", side_effect=fail_then_succeed):
            poller.start(initial_poll=False)

            poller.request_refresh("failure-1")
            assert wait_for_spy(completed)
            assert completed.at(completed.count() - 1)[0]["consecutive_failures"] == 1
            assert poller._current_backoff == 2

            poller.request_refresh("failure-2")
            assert wait_for_condition(lambda: completed.count() >= 2)
            assert completed.at(1)[0]["consecutive_failures"] == 2
            assert poller._current_backoff == 4

            poller.request_refresh("failure-3")
            assert wait_for_condition(lambda: completed.count() >= 3)
            assert completed.at(2)[0]["consecutive_failures"] == 3
            assert poller._current_backoff == 8

            poller.request_refresh("success")
            assert wait_for_condition(lambda: completed.count() >= 4)
            assert completed.at(3)[0]["success"] is True
            assert completed.at(3)[0]["consecutive_failures"] == 0
            assert poller._current_backoff == poller._initial_backoff
    finally:
        stop_poller(poller)


def test_snapshot_retention(qapp, tmp_path):
    poller, cm = make_poller(tmp_path)
    completed = QSignalSpy(poller.poll_completed)

    state_a = {"locked": True, "owner": "A", "session_id": "sess_A"}

    try:
        with patch.object(cm, "get_lock_status", return_value=state_a):
            poller.start(initial_poll=False)
            poller.request_refresh("success")
            assert wait_for_spy(completed)
            first = poller.get_last_snapshot()
            assert first is not None
            assert first.poll_status == "success"
            assert first.remote_lock["owner"] == "A"

        def failing_get_lock():
            raise RuntimeError("Simulated failure")

        with patch.object(cm, "get_lock_status", side_effect=failing_get_lock):
            before_count = completed.count()
            poller.request_refresh("failure")
            assert wait_for_condition(lambda: completed.count() > before_count)

            second = poller.get_last_snapshot()
            assert second is not None
            assert second.poll_status == "error"
            assert second.is_stale is True
            assert second.remote_lock["owner"] == "A"
            assert second.queue == first.queue
            assert second.version == first.version
    finally:
        stop_poller(poller)
