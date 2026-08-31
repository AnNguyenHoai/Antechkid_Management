from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot


class _QtEventBridge(QObject):
    """Deliver EventBus publications on the thread owning this bridge.

    RuntimeSyncService performs network/filesystem work from a Python worker
    thread, while several EventBus subscribers are Qt widgets. Publishing those
    events directly lets UI callbacks execute in the worker thread. Qt requires
    QObject/UI work to stay in the receiver's thread, so this bridge converts
    worker-thread publishes into queued Qt deliveries.
    """

    event_ready = Signal(object)

    def __init__(self, event_bus: Any) -> None:
        super().__init__()
        self._event_bus = event_bus
        self.event_ready.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _dispatch(self, event: object) -> None:
        self._event_bus.publish(event)


class ThreadSafeEventBusProxy:
    """Small EventBus-compatible publisher safe for worker-thread services."""

    def __init__(self, event_bus: Any) -> None:
        self._event_bus = event_bus
        # Created while RuntimeSyncService is constructed on the Qt main
        # thread; therefore the bridge's affinity is the GUI thread.
        self._bridge = _QtEventBridge(event_bus)

    def publish(self, event: object) -> None:
        self._bridge.event_ready.emit(event)
