# -*- coding: utf-8 -*-
"""Process-local Offline READ fence. Never confers Git/WRITE authority.

A closed fence is the startup default, so existing online callers are
unaffected. Only a verified reconnect may clear an activated fence.
"""
from __future__ import annotations

import threading

_lock = threading.RLock()
_offline_read = False


def offline_read_active() -> bool:
    with _lock:
        return _offline_read


def set_offline_read(value: bool) -> None:
    global _offline_read
    with _lock:
        _offline_read = bool(value)
