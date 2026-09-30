# -*- coding: utf-8 -*-
"""Windows file-lock diagnostics for destructive recovery.

Uses the native Restart Manager API to identify processes that currently hold a
resource. The helper is diagnostic-only: it never terminates applications or
changes lock ownership.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileLockOwner:
    pid: int
    application_name: str
    service_short_name: str = ""

    def describe(self) -> str:
        service = f", service={self.service_short_name}" if self.service_short_name else ""
        name = self.application_name or "unknown"
        return f"pid={self.pid}, app={name}{service}"


def windows_lock_owners(path: Path) -> list[FileLockOwner]:
    """Return Windows Restart Manager owners for *path*.

    Non-Windows callers get an empty result. Any Restart Manager API failure is
    raised to the caller so recovery diagnostics do not silently claim a file is
    unlocked when ownership could not be determined.
    """
    if os.name != "nt":
        return []

    import ctypes
    from ctypes import wintypes

    ERROR_SUCCESS = 0
    ERROR_MORE_DATA = 234
    CCH_RM_SESSION_KEY = 32
    CCH_RM_MAX_APP_NAME = 255
    CCH_RM_MAX_SVC_NAME = 63

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class RM_UNIQUE_PROCESS(ctypes.Structure):
        _fields_ = [("dwProcessId", wintypes.DWORD), ("ProcessStartTime", FILETIME)]

    class RM_PROCESS_INFO(ctypes.Structure):
        _fields_ = [
            ("Process", RM_UNIQUE_PROCESS),
            ("strAppName", wintypes.WCHAR * (CCH_RM_MAX_APP_NAME + 1)),
            ("strServiceShortName", wintypes.WCHAR * (CCH_RM_MAX_SVC_NAME + 1)),
            ("ApplicationType", wintypes.DWORD),
            ("AppStatus", wintypes.ULONG),
            ("TSSessionId", wintypes.DWORD),
            ("bRestartable", wintypes.BOOL),
        ]

    rstrtmgr = ctypes.WinDLL("Rstrtmgr.dll", use_last_error=True)
    rstrtmgr.RmStartSession.argtypes = [
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
        wintypes.LPWSTR,
    ]
    rstrtmgr.RmStartSession.restype = wintypes.DWORD
    rstrtmgr.RmRegisterResources.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        ctypes.POINTER(wintypes.LPCWSTR),
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.c_void_p,
    ]
    rstrtmgr.RmRegisterResources.restype = wintypes.DWORD
    rstrtmgr.RmGetList.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(RM_PROCESS_INFO),
        ctypes.POINTER(wintypes.DWORD),
    ]
    rstrtmgr.RmGetList.restype = wintypes.DWORD
    rstrtmgr.RmEndSession.argtypes = [wintypes.DWORD]
    rstrtmgr.RmEndSession.restype = wintypes.DWORD

    session = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(CCH_RM_SESSION_KEY + 1)
    result = rstrtmgr.RmStartSession(ctypes.byref(session), 0, key)
    if result != ERROR_SUCCESS:
        raise OSError(result, f"RmStartSession failed with code {result}")

    try:
        resources = (wintypes.LPCWSTR * 1)(str(Path(path).resolve()))
        result = rstrtmgr.RmRegisterResources(session, 1, resources, 0, None, 0, None)
        if result != ERROR_SUCCESS:
            raise OSError(result, f"RmRegisterResources failed with code {result}")

        needed = wintypes.UINT(0)
        count = wintypes.UINT(0)
        reasons = wintypes.DWORD(0)
        result = rstrtmgr.RmGetList(
            session,
            ctypes.byref(needed),
            ctypes.byref(count),
            None,
            ctypes.byref(reasons),
        )
        if result == ERROR_SUCCESS and needed.value == 0:
            return []
        if result != ERROR_MORE_DATA:
            raise OSError(result, f"RmGetList(size) failed with code {result}")

        entries = (RM_PROCESS_INFO * needed.value)()
        count = wintypes.UINT(needed.value)
        result = rstrtmgr.RmGetList(
            session,
            ctypes.byref(needed),
            ctypes.byref(count),
            entries,
            ctypes.byref(reasons),
        )
        if result != ERROR_SUCCESS:
            raise OSError(result, f"RmGetList(data) failed with code {result}")

        return [
            FileLockOwner(
                pid=int(entries[index].Process.dwProcessId),
                application_name=str(entries[index].strAppName),
                service_short_name=str(entries[index].strServiceShortName),
            )
            for index in range(count.value)
        ]
    finally:
        rstrtmgr.RmEndSession(session)


def format_lock_owners(owners: list[FileLockOwner]) -> str:
    if not owners:
        return "none reported by Windows Restart Manager"
    return "; ".join(owner.describe() for owner in owners)
