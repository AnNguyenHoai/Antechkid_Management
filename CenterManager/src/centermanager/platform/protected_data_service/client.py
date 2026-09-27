# -*- coding: utf-8 -*-
"""Desktop-side client for the protected-data Windows service.

The client never receives SQLCipher key material and cannot issue raw SQL.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Mapping

from .broker import MAX_RESPONSE_BYTES
from .protocol import PROTOCOL_VERSION, SERVICE_PIPE_NAME, ProtectedDataOperation


class ProtectedDataClientError(RuntimeError):
    pass


def _load_win32():
    if os.name != "nt":
        raise ProtectedDataClientError("Protected-data service client is Windows-only.")
    try:
        import win32file  # type: ignore
        import win32pipe  # type: ignore
    except ImportError as exc:
        raise ProtectedDataClientError("pywin32 is required for protected-data IPC.") from exc
    return win32file, win32pipe


class ProtectedDataClient:
    def __init__(self, pipe_name: str = SERVICE_PIPE_NAME, timeout_ms: int = 5000) -> None:
        self._pipe_name = pipe_name
        self._timeout_ms = int(timeout_ms)

    def _call(self, operation: ProtectedDataOperation,
              payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        win32file, win32pipe = _load_win32()
        request_id = uuid.uuid4().hex
        message = json.dumps(
            {
                "version": PROTOCOL_VERSION,
                "request_id": request_id,
                "operation": operation.value,
                "payload": dict(payload or {}),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            win32pipe.WaitNamedPipe(self._pipe_name, self._timeout_ms)
            handle = win32file.CreateFile(
                self._pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
        except Exception as exc:
            raise ProtectedDataClientError("AnTechKidsData service is unavailable.") from exc
        try:
            win32pipe.SetNamedPipeHandleState(handle, win32pipe.PIPE_READMODE_MESSAGE, None, None)
            win32file.WriteFile(handle, message)
            _, raw = win32file.ReadFile(handle, MAX_RESPONSE_BYTES)
        except Exception as exc:
            raise ProtectedDataClientError("Protected-data IPC failed.") from exc
        finally:
            handle.Close()
        try:
            response = json.loads(bytes(raw).decode("utf-8"))
        except Exception as exc:
            raise ProtectedDataClientError("Protected-data service returned an invalid response.") from exc
        if not isinstance(response, dict) or response.get("request_id") != request_id:
            raise ProtectedDataClientError("Protected-data response correlation failed.")
        if response.get("version") != PROTOCOL_VERSION:
            raise ProtectedDataClientError("Protected-data protocol version mismatch.")
        if response.get("ok") is not True:
            raise ProtectedDataClientError(str(response.get("error") or "Protected-data request failed."))
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise ProtectedDataClientError("Protected-data result must be an object.")
        return result

    def health(self) -> dict[str, Any]:
        return self._call(ProtectedDataOperation.HEALTH)

    def validate_database(self) -> dict[str, Any]:
        return self._call(ProtectedDataOperation.VALIDATE_DATABASE)

    def create_backup(self, label: str = "manual") -> dict[str, Any]:
        return self._call(ProtectedDataOperation.CREATE_BACKUP, {"label": label})
