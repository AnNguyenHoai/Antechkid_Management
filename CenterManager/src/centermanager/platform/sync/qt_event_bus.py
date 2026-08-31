from __future__ import annotations

from typing import Any, Callable, List

from PySide6.QtCore import QObject, Qt, Signal, Slot


class _QtEventBridge(QObject):
    """Marshal worker-thread EventBus publications onto the GUI thread."""

    event_ready = Signal(object)

    def __init__(self, dispatch: Callable[[object], None]) -> None:
        super().__init__()
        self._dispatch_callback = dispatch
        self.event_ready.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _dispatch(self, event: object) -> None:
        self._dispatch_callback(event)


class ThreadSafeEventBusProxy:
    """EventBus-compatible publisher with the real EventBus subscription API.

    Publishing from worker threads is queued through a Qt bridge. Subscription
    registration remains delegated to the underlying EventBus so existing code
    that accesses ``_event_bus.register(...)`` continues to work.
    """

    def __init__(self, event_bus: Any) -> None:
        self._event_bus = event_bus
        self._bridge = _QtEventBridge(self._dispatch)

    def _dispatch(self, event: object) -> None:
        self._event_bus.publish(event)

    def publish(self, event: object) -> None:
        self._bridge.event_ready.emit(event)

    def register(self, event_type: Any, callback: Callable[[Any], None]) -> None:
        self._event_bus.register(event_type, callback)

    def unregister(self, event_type: Any, callback: Callable[[Any], None]) -> None:
        unregister = getattr(self._event_bus, "unregister", None)
        if unregister is not None:
            unregister(event_type, callback)

    def subscribe(self, *args: Any, **kwargs: Any) -> Any:
        subscribe = getattr(self._event_bus, "subscribe", None)
        if subscribe is None:
            raise AttributeError("Underlying EventBus does not provide subscribe()")
        return subscribe(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._event_bus, name)
