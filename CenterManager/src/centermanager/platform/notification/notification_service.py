from typing import Callable, Optional

class NotificationService:
    def __init__(self):
        self._listeners: list[Callable[[str, str], None]] = []

    def notify(self, message: str, severity: str = "info") -> None:
        """Notify all listeners with a message and severity level."""
        for listener in self._listeners:
            listener(message, severity)

    def add_listener(self, callback: Callable[[str, str], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, str], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)