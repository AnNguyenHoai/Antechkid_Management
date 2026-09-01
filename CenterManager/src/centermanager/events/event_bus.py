# -*- coding: utf-8 -*-
"""
Thread-safe in-memory event bus with Qt-thread marshalling.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Type, Callable, Any

from PySide6.QtCore import QObject, Qt, Signal, Slot, QThread

from centermanager.events.event import Event, EventHandler

logger = logging.getLogger(__name__)


class _EventBridge(QObject):
    """Own the Qt signal in the GUI thread and queue worker publications."""

    event_ready = Signal(object)

    def __init__(self, dispatch: Callable[[Event], None]) -> None:
        super().__init__()
        self._dispatch = dispatch
        self.event_ready.connect(
            self._dispatch_event,
            Qt.ConnectionType.QueuedConnection,
        )

    @Slot(object)
    def _dispatch_event(self, event: object) -> None:
        self._dispatch(event)  # type: ignore[arg-type]


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[Type[Event], List[EventHandler]] = {}
        self._handlers_lock = threading.RLock()

        # EventBus is created after QApplication in the application bootstrap.
        # Creating the bridge here guarantees that its QObject affinity belongs
        # to the GUI thread before any background poller/sync worker starts.
        self._qt_thread: QThread | None = None
        self._bridge: _EventBridge | None = None
        try:
            self._qt_thread = QThread.currentThread()
            self._bridge = _EventBridge(self._dispatch)
        except Exception:
            # Keep the EventBus usable in non-Qt/unit-test environments.
            logger.debug("Qt event bridge unavailable; using direct dispatch", exc_info=True)
            self._qt_thread = None
            self._bridge = None

    def register(self, event_class: Type[Event], handler: EventHandler) -> None:
        """Register a handler for an event type."""
        with self._handlers_lock:
            if event_class not in self._handlers:
                self._handlers[event_class] = []
            self._handlers[event_class].append(handler)
        logger.debug(f"Registered handler {handler.__class__.__name__} for {event_class.__name__}")

    def unregister(self, event_class: Type[Event], handler: EventHandler) -> None:
        """Unregister a previously registered handler."""
        with self._handlers_lock:
            handlers = self._handlers.get(event_class)
            if not handlers:
                return
            try:
                handlers.remove(handler)
            except ValueError:
                return
            if not handlers:
                self._handlers.pop(event_class, None)

    def publish(self, event: Event) -> None:
        """Publish safely; worker-thread publications are queued to GUI."""
        if self._bridge is not None:
            self._bridge.event_ready.emit(event)
            return
        self._dispatch(event)

    def _dispatch(self, event: Event) -> None:
        event_class = type(event)
        with self._handlers_lock:
            handlers = list(self._handlers.get(event_class, []))

        for handler in handlers:
            try:
                if hasattr(handler, "handle"):
                    handler.handle(event)
                elif callable(handler):
                    handler(event)
                else:
                    logger.warning(
                        f"Handler {handler} is not callable and has no handle method."
                    )
            except Exception as e:
                logger.exception(
                    f"Error handling event {event_class.__name__} with {handler}: {e}"
                )
