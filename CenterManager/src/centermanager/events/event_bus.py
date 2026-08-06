# -*- coding: utf-8 -*-
"""
Simple in-memory event bus.
"""
import logging
from typing import Dict, List, Type, Callable

from centermanager.events.event import Event, EventHandler

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[Type[Event], List[EventHandler]] = {}

    def register(self, event_class: Type[Event], handler: EventHandler) -> None:
        """Register a handler for an event type."""
        if event_class not in self._handlers:
            self._handlers[event_class] = []
        self._handlers[event_class].append(handler)
        logger.debug(f"Registered handler {handler.__class__.__name__} for {event_class.__name__}")

    def publish(self, event: Event) -> None:
        event_class = type(event)
        handlers = self._handlers.get(event_class, [])
        for handler in handlers:
            try:
                if hasattr(handler, 'handle'):
                    handler.handle(event)
                elif callable(handler):
                    handler(event)
                else:
                    logger.warning(f"Handler {handler} is not callable and has no handle method.")
            except Exception as e:
                logger.exception(f"Error handling event {event_class.__name__} with {handler}: {e}")