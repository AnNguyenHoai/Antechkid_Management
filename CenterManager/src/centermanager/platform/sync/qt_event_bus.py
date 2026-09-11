from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot, QThread


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
    """EventBus-compatible publisher without creating QObjects in worker threads.

    The proxy itself can be constructed anywhere. The Qt bridge is created lazily
    when ``publish()`` is first used on a Qt-aware thread. For the application
    startup path, ``bind_to_current_thread()`` is called from the GUI thread so
    all later worker publications are queued back to that thread.
    """

    def __init__(self, event_bus: Any) -> None:
        self._event_bus = event_bus
        self._bridge: _QtEventBridge | None = None
        self._bound_thread: QThread | None = None

    def bind_to_current_thread(self) -> None:
        """Create the Qt bridge on the current Qt thread (normally GUI thread)."""
        current = QThread.currentThread()
        if self._bridge is not None:
            return
        self._bridge = _QtEventBridge(self._dispatch)
        self._bound_thread = current

    def _dispatch(self, event: object) -> None:
        self._event_bus.publish(event)

    def publish(self, event: object) -> None:
        # If a GUI-bound bridge exists, queued delivery is the safe path.
        if self._bridge is not None:
            self._bridge.event_ready.emit(event)
            return

        # No Qt bridge has been bound yet. This must only occur before the
        # background sync service starts; publish synchronously rather than
        # creating a QObject from an arbitrary worker thread.
        self._event_bus.publish(event)

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
