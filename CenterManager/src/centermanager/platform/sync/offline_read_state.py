# -*- coding: utf-8 -*-
"""Process-local Offline READ fence. Never confers Git/WRITE authority.

A closed fence is the startup default, so existing online callers are
unaffected. Only a verified reconnect may clear an activated fence.
"""
from __future__ import annotations

import threading

_lock = threading.RLock()
_offline_read = False
_receipt_read_only = False


def receipt_read_only_active() -> bool:
    """A Recovery receipt failure is not cleared by an unrelated Git reconnect."""
    with _lock:
        return _receipt_read_only


def protect_read_only_for_process() -> None:
    """Monotonic WRITE fence until a new validated application bootstrap.

    No background sync or public setter can clear this after loss of the
    Recovery WRITE receipt. The operator may restart only after repair.
    """
    global _offline_read, _receipt_read_only
    with _lock:
        _receipt_read_only = True
        _offline_read = True


def offline_read_active() -> bool:
    with _lock:
        return _offline_read or _receipt_read_only


def set_offline_read(value: bool) -> None:
    global _offline_read
    with _lock:
        # Reconnect can release a normal network outage fence, never a
        # failed Recovery receipt's process-lifetime WRITE protection.
        _offline_read = bool(value) or _receipt_read_only
