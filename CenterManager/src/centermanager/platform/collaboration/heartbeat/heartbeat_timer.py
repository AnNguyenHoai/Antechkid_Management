# -*- coding: utf-8 -*-
"""
HeartbeatTimer - Qt-based timer for periodic heartbeat updates.
"""
import logging
from typing import Optional

from PySide6.QtCore import QTimer

from centermanager.platform.collaboration.heartbeat.heartbeat_service import HeartbeatService

logger = logging.getLogger(__name__)


class HeartbeatTimer:
    """
    Wraps QTimer to drive HeartbeatService at a fixed interval.
    """

    def __init__(self, service: HeartbeatService, interval_ms: int = 10000):
        self._service = service
        self._interval_ms = interval_ms
        self._timer: Optional[QTimer] = None

    def start(self) -> None:
        """Start the timer."""
        if self._timer is not None and self._timer.isActive():
            logger.warning("Heartbeat timer already active")
            return

        self._timer = QTimer()
        self._timer.timeout.connect(self._service.update)
        self._timer.start(self._interval_ms)
        logger.info(f"Heartbeat timer started (interval={self._interval_ms}ms)")

    def stop(self) -> None:
        """Stop the timer."""
        if self._timer is not None and self._timer.isActive():
            self._timer.stop()
            self._timer = None
            logger.info("Heartbeat timer stopped")

    def is_active(self) -> bool:
        return self._timer is not None and self._timer.isActive()