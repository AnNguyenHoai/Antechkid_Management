# -*- coding: utf-8 -*-
"""Process-local Offline READ fence. Never confers Git/WRITE authority.

A closed fence is the startup default, so existing online callers are
unaffected. Only a verified reconnect may clear an activated fence.
"""
from __future__ import annotations

import threading

_lock = threading.RLock()
_offline_read = False
_recovery_read_only = False


def recovery_read_only_active() -> bool:
    """Recovery proof failure cannot be repaired merely by reconnecting Git."""
    with _lock:
        return _recovery_read_only


def protect_read_only_for_process() -> None:
    """Monotonic, process-lifetime WRITE fence on unverified Recovery receipt."""
    global _offline_read, _recovery_read_only
    with _lock:
        _recovery_read_only = True
        _offline_read = True


def offline_read_active() -> bool:
    with _lock:
        return _offline_read or _recovery_read_only


def set_offline_read(value: bool) -> None:
    global _offline_read
    with _lock:
        # A successful network reconnect must never clear Recovery protection.
        _offline_read = bool(value) or _recovery_read_only
