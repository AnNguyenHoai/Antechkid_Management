# -*- coding: utf-8 -*-
"""Regression tests for EventBus thread-dispatch semantics."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QThread

from centermanager.events.event import Event
from centermanager.events.event_bus import EventBus


@dataclass
class _TestEvent(Event):
    value: str


def _qt_app() -> QCoreApplication:
    app = QCoreApplication.instance()
    return app if app is not None else QCoreApplication([])


def test_publish_from_bridge_thread_dispatches_synchronously():
    """GUI/bridge-thread publications must be visible before publish returns."""
    _qt_app()
    bus = EventBus()
    received = []

    bus.register(_TestEvent, received.append)
    event = _TestEvent("sync")

    bus.publish(event)

    assert received == [event]


def test_publish_from_worker_thread_is_queued_to_bridge_thread():
    """Worker publications must be marshalled to the EventBus bridge thread."""
    app = _qt_app()
    bus = EventBus()
    received = []
    received_thread = []
    worker_done = threading.Event()

    def handler(event):
        received.append(event)
        received_thread.append(QThread.currentThread())

    bus.register(_TestEvent, handler)
    event = _TestEvent("worker")

    def worker():
        bus.publish(event)
        worker_done.set()

    thread = threading.Thread(target=worker)
    thread.start()
    assert worker_done.wait(timeout=2)
    thread.join(timeout=2)

    # The queued signal must not execute the handler on the worker thread.
    assert received == []

    deadline = time.monotonic() + 2
    while not received and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)

    assert received == [event]
    assert received_thread == [bus._qt_thread]


def test_worker_publication_preserves_fifo_order_on_bridge_thread():
    """Queued publications from one worker retain their publication order."""
    app = _qt_app()
    bus = EventBus()
    received = []

    bus.register(_TestEvent, received.append)

    def worker():
        for value in ("first", "second", "third"):
            bus.publish(_TestEvent(value))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=2)

    deadline = time.monotonic() + 2
    while len(received) < 3 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)

    assert [event.value for event in received] == ["first", "second", "third"]
