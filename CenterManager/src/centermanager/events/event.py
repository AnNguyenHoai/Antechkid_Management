# -*- coding: utf-8 -*-
"""
Base event and handler interfaces.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Event(ABC):
    """Base event class."""
    pass


class EventHandler(ABC):
    """Base event handler interface."""

    @abstractmethod
    def handle(self, event: Event) -> None:
        pass