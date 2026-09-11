# -*- coding: utf-8 -*-
"""Deterministic application clock.

Production code reads time through :class:`Clock` instead of calling
``datetime.now()``/``date.today()`` directly. Tests can inject a fixed clock.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Optional


class Clock:
    """Provide the current date/time through injectable callables."""

    def __init__(
        self,
        now_fn: Optional[Callable[[], datetime]] = None,
        today_fn: Optional[Callable[[], date]] = None,
    ) -> None:
        self._now_fn = now_fn or datetime.now
        self._today_fn = today_fn or date.today

    def now(self) -> datetime:
        """Return the current local date/time."""
        return self._now_fn()

    def today(self) -> date:
        """Return the current local date."""
        return self._today_fn()


_fixed_clock: Optional[Clock] = None


def get_clock() -> Clock:
    """Return the application clock singleton."""
    global _fixed_clock
    if _fixed_clock is None:
        _fixed_clock = Clock()
    return _fixed_clock


def set_clock(clock: Clock) -> None:
    """Replace the application clock, primarily for deterministic tests."""
    global _fixed_clock
    _fixed_clock = clock


def reset_clock() -> None:
    """Reset the application clock to system time."""
    global _fixed_clock
    _fixed_clock = Clock()
