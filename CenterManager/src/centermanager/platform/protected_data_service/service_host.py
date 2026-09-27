# -*- coding: utf-8 -*-
"""Windows service host for the SEC-02 protected-data identity.

Phase A intentionally establishes the dedicated service identity and lifecycle
without exposing database/key operations yet. Phase B will attach the broker to
this process. The raw SQLCipher workspace key must never be returned to clients.
"""
from __future__ import annotations

import os
import sys

from .protocol import SERVICE_NAME


class ProtectedDataServiceUnavailable(RuntimeError):
    pass


def _load_pywin32():
    if os.name != "nt":
        raise ProtectedDataServiceUnavailable(
            "The protected data service is available only on Windows."
        )
    try:
        import servicemanager  # type: ignore
        import win32event  # type: ignore
        import win32service  # type: ignore
        import win32serviceutil  # type: ignore
    except ImportError as exc:
        raise ProtectedDataServiceUnavailable(
            "pywin32 is required to install/run the AnTechKidsData Windows service."
        ) from exc
    return servicemanager, win32event, win32service, win32serviceutil


def service_class():
    servicemanager, win32event, win32service, win32serviceutil = _load_pywin32()

    class AnTechKidsDataService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = "AnTech Kids Protected Data Service"
        _svc_description_ = (
            "Owns protected CenterManager database/key storage. "
            "Database broker operations are enabled only after SEC-02 Phase B."
        )

        def __init__(self, args):
            super().__init__(args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self):
            servicemanager.LogInfoMsg(
                f"{SERVICE_NAME} started (SEC-02 identity host; broker disabled)"
            )
            win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)
            servicemanager.LogInfoMsg(f"{SERVICE_NAME} stopped")

    return AnTechKidsDataService, win32serviceutil


def main(argv: list[str] | None = None) -> int:
    """Install/start/stop/remove using pywin32 ServiceFramework commands."""
    service, win32serviceutil = service_class()
    original = sys.argv
    try:
        if argv is not None:
            sys.argv = [original[0], *argv]
        win32serviceutil.HandleCommandLine(service)
        return 0
    finally:
        sys.argv = original


if __name__ == "__main__":
    raise SystemExit(main())
